from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional

from app.core.database import get_db
from app.core.dependencies import get_current_user, require_admin
from app.models.schemas import ServerRegisterRequest, HeartbeatRequest
from app.services import server_service

router = APIRouter(tags=["Servers"])


@router.post("/servers/register")
def register_server(
    payload: ServerRegisterRequest,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Any logged-in user can register a server as a provider.
    In production you'd require role='provider' — for now any user can do it.
    """
    result = server_service.register_server(
        db=db,
        provider_id=str(current_user.id),
        data=payload.model_dump()
    )
    return result


@router.get("/servers")
def list_servers(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    List all servers. In production this would be admin-only.
    For now any logged-in user can see the list.
    """
    servers = server_service.get_all_servers(db)
    return [
        {
            "id": str(s.id),
            "name": s.name,
            "gpu_model": s.gpu_model,
            "gpu_count": s.gpu_count,
            "vram_mb": s.vram_mb,
            "location_country": s.location_country,
            "location_region": s.location_region,
            "tokens_per_gpu_hour": s.tokens_per_gpu_hour,
            "status": s.status,
            "max_concurrent_jobs": s.max_concurrent_jobs,
            "last_heartbeat_at": s.last_heartbeat_at,
            "active_jobs": s.active_jobs,
        }
        for s in servers
    ]


@router.get("/servers/available")
def list_available_servers(
    gpu_model: Optional[str] = Query(default=None),
    min_vram_mb: int = Query(default=0),
    db: Session = Depends(get_db)
):
    """
    Public endpoint — shows servers that can accept jobs right now.
    The job scheduler uses this to find where to send work.
    """
    servers = server_service.get_available_servers(db, gpu_model, min_vram_mb)
    return [
        {
            "id": str(s.id),
            "name": s.name,
            "gpu_model": s.gpu_model,
            "vram_mb": s.vram_mb,
            "tokens_per_gpu_hour": s.tokens_per_gpu_hour,
            "free_slots": s.max_concurrent_jobs - s.active_jobs,
        }
        for s in servers
    ]


@router.post("/agent/heartbeat")
def heartbeat(
    payload: HeartbeatRequest,
    x_api_key: str = Header(...),    # agent sends key in X-Api-Key header
    db: Session = Depends(get_db)
):
    """
    Called by the agent every 30s.
    No JWT needed — uses API key authentication instead.
    Header name: X-Api-Key
    """
    # Verify the API key
    server = server_service.verify_api_key(db, x_api_key)
    if not server:
        raise HTTPException(status_code=401, detail="Invalid API key")

    # Record the heartbeat metrics
    server_service.record_heartbeat(
        db=db,
        server_id=str(server.id),
        metrics=payload.model_dump()
    )

    return {
        "status": "ok",
        "server_id": str(server.id),
        "message": "Heartbeat received"
    }


@router.post("/servers/{server_id}/approve")
def approve_server(
    server_id: str,
    current_user=Depends(require_admin),   # admin only
    db: Session = Depends(get_db)
):
    """
    Admin approves a pending server so it enters the available pool.
    """
    return server_service.approve_server(db, server_id, str(current_user.id))