from sqlalchemy.orm import Session
from sqlalchemy import text
from fastapi import HTTPException
import uuid
import secrets
import hashlib


def generate_api_key() -> tuple[str, str]:
    """
    Generate a secure API key for a GPU server agent.

    Returns two values:
    - raw_key: shown to the provider ONCE, never stored
    - hashed_key: stored in DB, used to verify future requests

    secrets.token_hex(32) gives us 64 random hex characters.
    We prefix with 'gpukey_' so it's easy to identify.
    """
    raw_key = f"gpukey_{secrets.token_hex(32)}"
    hashed_key = hashlib.sha256(raw_key.encode()).hexdigest()
    return raw_key, hashed_key


def verify_api_key(db: Session, raw_key: str):
    """
    Given a raw API key from the request header,
    hash it and look up the matching server in DB.

    Returns the server row if found, None if not.
    This is called on every heartbeat from the agent.
    """
    hashed = hashlib.sha256(raw_key.encode()).hexdigest()
    server = db.execute(
        text("""
            SELECT * FROM gpu_servers
            WHERE api_key_hash = :hash
            AND status != 'banned'
        """),
        {"hash": hashed}
    ).fetchone()
    return server


def register_server(db: Session, provider_id: str, data: dict):
    """
    Register a new GPU server for a provider.

    Steps:
    1. Generate API key pair (raw + hashed)
    2. Look up the correct token price from gpu_pricing table
    3. Insert server record into gpu_servers
    4. Return the raw API key (shown only once)
    """

    # Step 1: Generate API key
    raw_key, hashed_key = generate_api_key()

    # Step 2: Auto-detect price from gpu_pricing if not set
    # We use ILIKE for case-insensitive pattern matching
    pricing = db.execute(
        text("""
            SELECT tokens_per_gpu_hour
            FROM gpu_pricing
            WHERE :gpu_model ILIKE gpu_model_pattern
            AND is_active = true
            LIMIT 1
        """),
        {"gpu_model": data["gpu_model"]}
    ).fetchone()

    # Use detected price, or fall back to what provider specified
    tokens_per_hour = pricing.tokens_per_gpu_hour if pricing else data["tokens_per_gpu_hour"]

    # Step 3: Insert the server
    server_id = str(uuid.uuid4())
    db.execute(
        text("""
            INSERT INTO gpu_servers (
                id, provider_id, name, gpu_model, gpu_count,
                vram_mb, location_country, location_region,
                cuda_version, max_concurrent_jobs,
                tokens_per_gpu_hour, api_key_hash, api_key_prefix,
                status
            ) VALUES (
                :id, :provider_id, :name, :gpu_model, :gpu_count,
                :vram_mb, :location_country, :location_region,
                :cuda_version, :max_concurrent_jobs,
                :tokens_per_gpu_hour, :api_key_hash, :api_key_prefix,
                'pending'
            )
        """),
        {
            "id": server_id,
            "provider_id": provider_id,
            "name": data["name"],
            "gpu_model": data["gpu_model"],
            "gpu_count": data["gpu_count"],
            "vram_mb": data["vram_mb"],
            "location_country": data["location_country"],
            "location_region": data.get("location_region"),
            "cuda_version": data.get("cuda_version"),
            "max_concurrent_jobs": data["max_concurrent_jobs"],
            "tokens_per_gpu_hour": tokens_per_hour,
            "api_key_hash": hashed_key,
            "api_key_prefix": raw_key[:12],   # store first 12 chars for display
        }
    )
    db.commit()

    return {
        "message": "Server registered. Save your API key — it won't be shown again.",
        "server_id": server_id,
        "api_key": raw_key,       # shown ONCE to provider
        "name": data["name"],
        "tokens_per_gpu_hour": tokens_per_hour,
    }


def record_heartbeat(db: Session, server_id: str, metrics: dict):
    """
    Called every 30s by the agent running on the GPU server.

    Does two things:
    1. Insert a row into server_heartbeats (time-series metrics)
    2. Update last_heartbeat_at and status='online' on the server
    """

    # Insert metrics snapshot
    db.execute(
        text("""
            INSERT INTO server_heartbeats (
                server_id, cpu_pct, gpu_pct,
                vram_used_mb, vram_free_mb,
                temp_celsius, jobs_running
            ) VALUES (
                :server_id, :cpu_pct, :gpu_pct,
                :vram_used_mb, :vram_free_mb,
                :temp_celsius, :jobs_running
            )
        """),
        {
            "server_id": server_id,
            "cpu_pct": metrics.get("cpu_pct", 0),
            "gpu_pct": metrics.get("gpu_pct", 0),
            "vram_used_mb": metrics.get("vram_used_mb", 0),
            "vram_free_mb": metrics.get("vram_free_mb", 0),
            "temp_celsius": metrics.get("temp_celsius", 0),
            "jobs_running": metrics.get("jobs_running", 0),
        }
    )

    # Mark server as online and update heartbeat timestamp
    db.execute(
        text("""
            UPDATE gpu_servers
            SET last_heartbeat_at = NOW(),
                status = 'online'
            WHERE id = :server_id
        """),
        {"server_id": server_id}
    )
    db.commit()


def get_all_servers(db: Session):
    """
    Return all servers with their active job count.
    Used by admin to monitor the pool.
    """
    servers = db.execute(
        text("""
            SELECT
                s.*,
                COALESCE(
                    (SELECT COUNT(*) FROM jobs j
                     WHERE j.server_id = s.id
                     AND j.status IN ('dispatched', 'running')),
                0) AS active_jobs
            FROM gpu_servers s
            ORDER BY s.created_at DESC
        """)
    ).fetchall()
    return servers


def get_available_servers(db: Session, gpu_model: str = None, min_vram_mb: int = 0):
    servers = db.execute(
        text("""
            SELECT
                s.*,
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
              AND (
                SELECT COUNT(*) FROM jobs j
                WHERE j.server_id = s.id
                AND j.status IN ('dispatched', 'running')
              ) < s.max_concurrent_jobs
            ORDER BY s.tokens_per_gpu_hour ASC
        """),
        {
            "min_vram": min_vram_mb,
            "gpu_model": f"%{gpu_model}%" if gpu_model else None,
        }
    ).fetchall()
    return servers


def approve_server(db: Session, server_id: str, admin_id: str):
    """
    Admin approves a pending server.
    Only approved servers appear in the available pool.
    """
    db.execute(
        text("""
            UPDATE gpu_servers
            SET status = 'online',
                approved_at = NOW(),
                approved_by = :admin_id
            WHERE id = :server_id
        """),
        {"server_id": server_id, "admin_id": admin_id}
    )
    db.commit()
    return {"message": "Server approved and now online"}