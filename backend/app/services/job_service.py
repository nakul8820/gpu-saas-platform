from sqlalchemy.orm import Session
from sqlalchemy import text
from fastapi import HTTPException
import uuid


def estimate_token_cost(tokens_per_gpu_hour: int, max_runtime_minutes: int, gpu_count: int) -> int:
    """
    Calculate how many tokens to lock at job submission.

    Formula: (tokens_per_hour / 60) * max_runtime_minutes * gpu_count
    We add a 20% buffer so we lock slightly more than the estimate.
    This protects against slight overruns.

    Example:
      Server charges 100 tokens/hour
      Job max runtime = 30 minutes
      GPU count = 1
      Raw estimate = (100/60) * 30 * 1 = 50 tokens
      With 20% buffer = 60 tokens locked
    """
    raw_estimate = (tokens_per_gpu_hour / 60) * max_runtime_minutes * gpu_count
    buffered = int(raw_estimate * 1.2)
    return max(buffered, 1)  # minimum 1 token


def find_best_server(db: Session, required_gpu_model: str = None, required_vram_mb: int = 0):
    """
    Find the best available server for this job.

    'Best' means:
    - Online and approved
    - Has enough VRAM
    - Has a free job slot
    - Cheapest price (lowest tokens_per_gpu_hour)

    Returns server row or None if nothing available.
    """
    query = text("""
        SELECT s.*,
            COALESCE(
                (SELECT COUNT(*) FROM jobs j
                 WHERE j.server_id = s.id
                 AND j.status IN ('dispatched', 'running')),
            0) AS active_jobs
        FROM gpu_servers s
        WHERE s.status = 'online'
          AND s.approved_at IS NOT NULL
          AND s.vram_mb >= :min_vram
          AND (:gpu_model IS NULL OR s.gpu_model ILIKE :gpu_model)
        ORDER BY s.tokens_per_gpu_hour ASC
    """)

    servers = db.execute(query, {
        "min_vram": required_vram_mb,
        "gpu_model": f"%{required_gpu_model}%" if required_gpu_model else None,
    }).fetchall()

    # Find first server with a free slot
    for server in servers:
        if server.active_jobs < server.max_concurrent_jobs:
            return server

    return None


def lock_tokens(db: Session, user_id: str, job_id: str, amount: int, current_balance: int):
    """
    Lock tokens at job submission.
    Inserts a negative 'job_lock' entry into the ledger.
    The trigger will reduce users.token_balance automatically.
    """
    new_balance = current_balance - amount

    db.execute(
        text("""
            INSERT INTO token_ledger
                (id, user_id, amount, entry_type, balance_after, ref_job_id, description)
            VALUES
                (:id, :user_id, :amount, 'job_lock', :balance_after, :job_id, :description)
        """),
        {
            "id": str(uuid.uuid4()),
            "user_id": user_id,
            "amount": -amount,          # negative = debit
            "balance_after": new_balance,
            "job_id": job_id,
            "description": f"Token lock for job {job_id[:8]}...",
        }
    )


def submit_job(db: Session, user_id: str, data: dict):
    """
    Full job submission flow:
    1. Find a matching server
    2. Estimate token cost
    3. Check user has enough balance
    4. Create the job record
    5. Lock the tokens
    6. Dispatch to server (in production: send HTTP request to agent)
    """

    # Step 1: Find best server
    server = find_best_server(
        db,
        required_gpu_model=data.get("required_gpu_model"),
        required_vram_mb=data.get("required_vram_mb", 0)
    )

    if not server:
        raise HTTPException(
            status_code=503,
            detail="No GPU servers available right now. Try again later."
        )

    # Step 2: Estimate token cost
    tokens_to_lock = estimate_token_cost(
        tokens_per_gpu_hour=server.tokens_per_gpu_hour,
        max_runtime_minutes=data["max_runtime_minutes"],
        gpu_count=data["gpu_count"]
    )

    # Step 3: Check balance
    user = db.execute(
        text("SELECT token_balance FROM users WHERE id = :uid"),
        {"uid": user_id}
    ).fetchone()

    if user.token_balance < tokens_to_lock:
        raise HTTPException(
            status_code=402,    # 402 = Payment Required
            detail=f"Insufficient tokens. Need {tokens_to_lock}, have {user.token_balance}. Please top up."
        )

    # Step 4: Create job record
    job_id = str(uuid.uuid4())
    db.execute(
        text("""
            INSERT INTO jobs (
                id, user_id, server_id, status,
                docker_image, command, env_vars,
                required_gpu_model, required_vram_mb,
                max_runtime_minutes, gpu_count, priority,
                tokens_locked, queued_at
            ) VALUES (
                :id, :user_id, :server_id, 'dispatched',
                :docker_image, :command, :env_vars,
                :required_gpu_model, :required_vram_mb,
                :max_runtime_minutes, :gpu_count, :priority,
                :tokens_locked, NOW()
            )
        """),
        {
            "id": job_id,
            "user_id": user_id,
            "server_id": str(server.id),
            "docker_image": data["docker_image"],
            "command": data.get("command"),
            "env_vars": str(data.get("env_vars", {})),
            "required_gpu_model": data.get("required_gpu_model"),
            "required_vram_mb": data.get("required_vram_mb", 0),
            "max_runtime_minutes": data["max_runtime_minutes"],
            "gpu_count": data["gpu_count"],
            "priority": data["priority"],
            "tokens_locked": tokens_to_lock,
        }
    )

    # Step 5: Lock tokens in ledger
    lock_tokens(db, user_id, job_id, tokens_to_lock, user.token_balance)

    db.commit()

    return {
        "message": "Job submitted successfully",
        "job_id": job_id,
        "server_id": str(server.id),
        "server_name": server.name,
        "gpu_model": server.gpu_model,
        "tokens_locked": tokens_to_lock,
        "status": "dispatched",
    }


def mark_job_running(db: Session, server_id: str, job_id: str):
    """
    Agent calls this when Docker container actually starts.
    Updates job status from 'dispatched' to 'running'.
    """
    job = db.execute(
        text("SELECT * FROM jobs WHERE id = :id AND server_id = :server_id"),
        {"id": job_id, "server_id": server_id}
    ).fetchone()

    if not job:
        raise HTTPException(status_code=404, detail="Job not found on this server")

    db.execute(
        text("""
            UPDATE jobs
            SET status = 'running', started_at = NOW()
            WHERE id = :id
        """),
        {"id": job_id}
    )
    db.commit()
    return {"message": "Job marked as running"}


def complete_job(db: Session, server_id: str, data: dict):
    """
    Agent calls this when the Docker container exits.

    Billing reconciliation:
    1. Calculate actual token cost from real gpu_seconds_used
    2. Debit actual cost from ledger
    3. Refund the difference (locked - actual)
    4. Credit provider earnings
    5. Mark job completed or failed
    """
    job_id = data["job_id"]
    exit_code = data["exit_code"]
    gpu_seconds = data["gpu_seconds_used"]

    # Get job details
    job = db.execute(
        text("SELECT * FROM jobs WHERE id = :id AND server_id = :server_id"),
        {"id": job_id, "server_id": server_id}
    ).fetchone()

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Get server pricing
    server = db.execute(
        text("SELECT * FROM gpu_servers WHERE id = :id"),
        {"id": server_id}
    ).fetchone()

    # Step 1: Calculate actual cost
    actual_tokens = max(
        int((gpu_seconds / 3600) * server.tokens_per_gpu_hour * job.gpu_count),
        1
    )
    tokens_locked = job.tokens_locked
    refund_amount = max(tokens_locked - actual_tokens, 0)

    # Get current balance for ledger entries
    user = db.execute(
        text("SELECT token_balance FROM users WHERE id = :uid"),
        {"uid": str(job.user_id)}
    ).fetchone()

    current_balance = user.token_balance

    # Step 2: Debit actual cost
    db.execute(
        text("""
            INSERT INTO token_ledger
                (id, user_id, amount, entry_type, balance_after, ref_job_id, description)
            VALUES
                (:id, :user_id, :amount, 'job_debit', :balance_after, :job_id, :description)
        """),
        {
            "id": str(uuid.uuid4()),
            "user_id": str(job.user_id),
            "amount": -actual_tokens,
            "balance_after": current_balance - actual_tokens,
            "job_id": job_id,
            "description": f"GPU usage: {gpu_seconds}s on {server.gpu_model}",
        }
    )
    current_balance -= actual_tokens

    # Step 3: Refund over-estimate if any
    if refund_amount > 0:
        db.execute(
            text("""
                INSERT INTO token_ledger
                    (id, user_id, amount, entry_type, balance_after, ref_job_id, description)
                VALUES
                    (:id, :user_id, :amount, 'job_lock_release', :balance_after, :job_id, :description)
            """),
            {
                "id": str(uuid.uuid4()),
                "user_id": str(job.user_id),
                "amount": refund_amount,
                "balance_after": current_balance + refund_amount,
                "job_id": job_id,
                "description": f"Refund: used {actual_tokens} of {tokens_locked} locked tokens",
            }
        )

    # Step 4: Credit provider earnings
    platform_fee = 0.20   # platform keeps 20%
    provider_tokens = int(actual_tokens * (1 - platform_fee))

    db.execute(
        text("""
            INSERT INTO provider_earnings
                (id, provider_id, server_id, job_id,
                 tokens_earned, gpu_seconds, platform_fee_pct, tokens_after_fee)
            VALUES
                (:id, :provider_id, :server_id, :job_id,
                 :tokens_earned, :gpu_seconds, 20.00, :tokens_after_fee)
        """),
        {
            "id": str(uuid.uuid4()),
            "provider_id": str(server.provider_id),
            "server_id": server_id,
            "job_id": job_id,
            "tokens_earned": actual_tokens,
            "gpu_seconds": gpu_seconds,
            "tokens_after_fee": provider_tokens,
        }
    )

    # Step 5: Mark job complete or failed
    final_status = "completed" if exit_code == 0 else "failed"

    db.execute(
        text("""
            UPDATE jobs SET
                status = :status,
                exit_code = :exit_code,
                gpu_seconds_used = :gpu_seconds,
                tokens_billed = :tokens_billed,
                peak_vram_mb = :peak_vram,
                error_message = :error_message,
                completed_at = NOW()
            WHERE id = :job_id
        """),
        {
            "status": final_status,
            "exit_code": exit_code,
            "gpu_seconds": gpu_seconds,
            "tokens_billed": actual_tokens,
            "peak_vram": data.get("peak_vram_mb"),
            "error_message": data.get("error_message"),
            "job_id": job_id,
        }
    )

    db.commit()

    return {
        "message": f"Job {final_status}",
        "job_id": job_id,
        "status": final_status,
        "gpu_seconds_used": gpu_seconds,
        "tokens_locked": tokens_locked,
        "tokens_billed": actual_tokens,
        "tokens_refunded": refund_amount,
    }


def get_user_jobs(db: Session, user_id: str):
    """Get all jobs for a user, newest first."""
    jobs = db.execute(
        text("""
            SELECT j.*, s.name as server_name, s.gpu_model
            FROM jobs j
            LEFT JOIN gpu_servers s ON s.id = j.server_id
            WHERE j.user_id = :uid
            ORDER BY j.queued_at DESC
        """),
        {"uid": user_id}
    ).fetchall()
    return jobs


def get_job_by_id(db: Session, job_id: str, user_id: str):
    """Get a single job — users can only see their own jobs."""
    job = db.execute(
        text("""
            SELECT j.*, s.name as server_name, s.gpu_model
            FROM jobs j
            LEFT JOIN gpu_servers s ON s.id = j.server_id
            WHERE j.id = :job_id AND j.user_id = :user_id
        """),
        {"job_id": job_id, "user_id": user_id}
    ).fetchone()

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job

def get_pending_job_for_server(db: Session, server_id: str):
    """
    Agent polls this every 5s.
    Returns the next dispatched job for this server, or None.
    We pick the highest priority job that was queued earliest.
    """
    job = db.execute(
        text("""
            SELECT * FROM jobs
            WHERE server_id = :server_id
            AND status = 'dispatched'
            ORDER BY priority DESC, queued_at ASC
            LIMIT 1
        """),
        {"server_id": server_id}
    ).fetchone()
    return job