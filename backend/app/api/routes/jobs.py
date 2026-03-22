from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.schemas import JobSubmitRequest, JobStartRequest, JobCompleteRequest
from app.services import job_service, server_service

router = APIRouter(tags=["Jobs"])


@router.post("/jobs")
def submit_job(
    payload: JobSubmitRequest,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Submit a GPU job.
    Tokens are locked immediately.
    Job is dispatched to the best available server.
    """
    return job_service.submit_job(
        db=db,
        user_id=str(current_user.id),
        data=payload.model_dump()
    )


@router.get("/jobs")
def list_jobs(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List all jobs submitted by the logged-in user."""
    jobs = job_service.get_user_jobs(db, str(current_user.id))
    return [
        {
            "id": str(j.id),
            "status": j.status,
            "docker_image": j.docker_image,
            "gpu_model": j.gpu_model,
            "server_name": j.server_name,
            "tokens_locked": j.tokens_locked,
            "tokens_billed": j.tokens_billed,
            "gpu_seconds_used": j.gpu_seconds_used,
            "queued_at": j.queued_at,
            "started_at": j.started_at,
            "completed_at": j.completed_at,
            "exit_code": j.exit_code,
        }
        for j in jobs
    ]


@router.get("/jobs/{job_id}")
def get_job(
    job_id: str,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get details of a single job."""
    job = job_service.get_job_by_id(db, job_id, str(current_user.id))
    return {
        "id": str(job.id),
        "status": job.status,
        "docker_image": job.docker_image,
        "gpu_model": job.gpu_model,
        "server_name": job.server_name,
        "tokens_locked": job.tokens_locked,
        "tokens_billed": job.tokens_billed,
        "gpu_seconds_used": job.gpu_seconds_used,
        "queued_at": job.queued_at,
        "started_at": job.started_at,
        "completed_at": job.completed_at,
        "exit_code": job.exit_code,
        "error_message": job.error_message,
    }


@router.post("/agent/job-start")
def job_start(
    payload: JobStartRequest,
    x_api_key: str = Header(...),
    db: Session = Depends(get_db)
):
    """
    Agent calls this when Docker container starts running.
    Uses API key auth — same as heartbeat.
    """
    server = server_service.verify_api_key(db, x_api_key)
    if not server:
        raise HTTPException(status_code=401, detail="Invalid API key")

    return job_service.mark_job_running(db, str(server.id), payload.job_id)


@router.post("/agent/job-complete")
def job_complete(
    payload: JobCompleteRequest,
    x_api_key: str = Header(...),
    db: Session = Depends(get_db)
):
    """
    Agent calls this when job finishes (success or failure).
    This triggers billing reconciliation:
    - Debits actual tokens used
    - Refunds over-estimate
    - Credits provider earnings
    """
    server = server_service.verify_api_key(db, x_api_key)
    if not server:
        raise HTTPException(status_code=401, detail="Invalid API key")

    return job_service.complete_job(db, str(server.id), payload.model_dump())


@router.get("/agent/pending-job")
def get_pending_job(
    x_api_key: str = Header(...),
    db: Session = Depends(get_db)
):
    """
    Agent polls this every 5s to check if a job is waiting.
    Returns the job details or empty dict if nothing pending.
    """
    server = server_service.verify_api_key(db, x_api_key)
    if not server:
        raise HTTPException(status_code=401, detail="Invalid API key")

    job = job_service.get_pending_job_for_server(db, str(server.id))

    if not job:
        return {"job": None}

    return {
        "job": {
            "id": str(job.id),
            "docker_image": job.docker_image,
            "command": job.command,
            "env_vars": job.env_vars,
            "max_runtime_minutes": job.max_runtime_minutes,
            "gpu_count": job.gpu_count,
        }
    }


@router.post("/agent/job-log")
def receive_log_chunk(
    x_api_key: str = Header(...),
    job_id: str = Query(...),
    chunk: str = Query(...),
    seq: int = Query(...),
    stream: str = Query(default="stdout"),
    db: Session = Depends(get_db)
):
    """
    Agent streams stdout/stderr chunks here in real time.
    Each chunk is stored in job_logs table.
    """
    server = server_service.verify_api_key(db, x_api_key)
    if not server:
        raise HTTPException(status_code=401, detail="Invalid API key")

    db.execute(
        text("""
            INSERT INTO job_logs (job_id, stream, chunk, seq)
            VALUES (:job_id, :stream, :chunk, :seq)
        """),
        {"job_id": job_id, "stream": stream, "chunk": chunk, "seq": seq}
    )
    db.commit()
    return {"ok": True}


@router.get("/jobs/{job_id}/logs")
def get_job_logs(
    job_id: str,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get all log chunks for a job in order.
    Used by the frontend log viewer.
    """
    job = job_service.get_job_by_id(db, job_id, str(current_user.id))

    logs = db.execute(
        text("""
            SELECT stream, chunk, seq, recorded_at
            FROM job_logs
            WHERE job_id = :job_id
            ORDER BY seq ASC
        """),
        {"job_id": job_id}
    ).fetchall()

    return {
        "job_id": job_id,
        "status": job.status,
        "logs": [
            {
                "stream": l.stream,
                "chunk": l.chunk,
                "seq": l.seq,
                "recorded_at": l.recorded_at,
            }
            for l in logs
        ]
    }