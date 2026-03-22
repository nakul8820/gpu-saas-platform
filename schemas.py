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
    id : str
    name : str
    token_amount : int
    price_inr : float
    bonus_tokens : int
    total_tokens : int # total_tokens + bonus_tokens

class BalanceResponse(BaseModel):
    balance: int
    email : str

class LedgerEntryResponse(BaseModel):
    id : str
    amount : int
    entry_type : str
    balance_after : int
    description : Optional[str]
    created_at : datetime

class LedgeHistoryResponse(BaseModel):
    entries: List[LedgerEntryResponse]
    total : int
    page : int
    page_size : int

class ManualTopUpRequest(BaseModel):
    package_id : str    # Which package