from pydantic import BaseModel, EmailStr, field_validator
from typing import Optional
from datetime import datetime
import re


class UserRegister(BaseModel):
    email: EmailStr
    password: str
    full_name: Optional[str] = None

    @field_validator("password")
    @classmethod
    def password_strength(cls, v):
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        if not re.search(r"[A-Z]", v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not re.search(r"[0-9]", v):
            raise ValueError("Password must contain at least one number")
        return v


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class UserResponse(BaseModel):
    id: str
    email: str
    full_name: Optional[str]
    role: str
    token_balance: int
    is_verified: bool
    created_at: datetime

    class Config:
        from_attributes = True


class RegisterResponse(BaseModel):
    message: str
    user: UserResponse
    tokens: TokenResponse


class TokenPackageResponse(BaseModel):
    id: str
    name: str
    token_amount: int
    price_inr: float
    bonus_tokens: int
    total_tokens: int


class BalanceResponse(BaseModel):
    balance: int
    email: str


class LedgerEntryResponse(BaseModel):
    id: str
    amount: int
    entry_type: str
    balance_after: int
    description: Optional[str]
    created_at: datetime


class LedgerHistoryResponse(BaseModel):
    entries: list[LedgerEntryResponse]
    total: int
    page: int
    page_size: int


class ManualTopUpRequest(BaseModel):
    package_id: str

class ServerRegisterRequest(BaseModel):
    name: str                        # e.g. "A100 Node 1"
    gpu_model: str                   # e.g. "NVIDIA A100 80GB"
    gpu_count: int = 1
    vram_mb: int                     # VRAM per GPU in MB
    location_country: str = "IN"
    location_region: Optional[str] = None   # e.g. "Mumbai"
    cuda_version: Optional[str] = None
    max_concurrent_jobs: int = 1
    tokens_per_gpu_hour: int         # how much to charge per hour


class ServerRegisterResponse(BaseModel):
    message: str
    server_id: str
    api_key: str          # shown ONCE — provider must save this
    name: str
    tokens_per_gpu_hour: int


class ServerResponse(BaseModel):
    id: str
    name: str
    gpu_model: str
    gpu_count: int
    vram_mb: int
    location_country: str
    location_region: Optional[str]
    tokens_per_gpu_hour: int
    status: str
    max_concurrent_jobs: int
    last_heartbeat_at: Optional[datetime]
    active_jobs: int


class HeartbeatRequest(BaseModel):
    cpu_pct: int = 0
    gpu_pct: int = 0
    vram_used_mb: int = 0
    vram_free_mb: int = 0
    temp_celsius: int = 0
    jobs_running: int = 0

# ── Job Schemas 

class JobSubmitRequest(BaseModel):
    docker_image: str              # e.g. "pytorch/pytorch:2.1.0-cuda12.1"
    command: Optional[list[str]] = None  # e.g. ["python", "train.py"]
    env_vars: Optional[dict] = {}        # environment variables
    required_gpu_model: Optional[str] = None  # None = any GPU
    required_vram_mb: int = 0
    max_runtime_minutes: int = 60
    gpu_count: int = 1
    priority: int = 5              # 1-10, higher = processed first


class JobResponse(BaseModel):
    id: str
    status: str
    docker_image: str
    tokens_locked: int
    tokens_billed: Optional[int]
    gpu_seconds_used: Optional[int]
    server_id: Optional[str]
    queued_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    exit_code: Optional[int]
    error_message: Optional[str]


class JobStartRequest(BaseModel):
    job_id: str                    # agent tells us which job started


class JobCompleteRequest(BaseModel):
    job_id: str
    exit_code: int                 # 0 = success, anything else = failed
    gpu_seconds_used: int          # actual GPU time used
    peak_vram_mb: Optional[int] = None
    error_message: Optional[str] = None