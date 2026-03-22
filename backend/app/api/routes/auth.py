from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.schemas import (
    UserRegister,
    UserLogin,
    TokenResponse,
    RefreshTokenRequest,
    UserResponse,
    RegisterResponse,
)
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
def register(payload: UserRegister, db: Session = Depends(get_db)):
    user, access_token, refresh_token = auth_service.register_user(
        db=db,
        email=payload.email,
        password=payload.password,
        full_name=payload.full_name,
    )

    return {
        "message": "Account created successfully",
        "user": {
            "id": str(user.id),
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role,
            "token_balance": user.token_balance,
            "is_verified": user.is_verified,
            "created_at": user.created_at,
        },
        "tokens": {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
        },
    }


@router.post("/login", response_model=RegisterResponse)
def login(payload: UserLogin, db: Session = Depends(get_db)):
    user, access_token, refresh_token = auth_service.login_user(
        db=db,
        email=payload.email,
        password=payload.password,
    )

    return {
        "message": "Login successful",
        "user": {
            "id": str(user.id),
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role,
            "token_balance": user.token_balance,
            "is_verified": user.is_verified,
            "created_at": user.created_at,
        },
        "tokens": {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
        },
    }


@router.post("/refresh", response_model=TokenResponse)
def refresh(payload: RefreshTokenRequest, db: Session = Depends(get_db)):
    new_access_token = auth_service.refresh_access_token(
        db=db,
        refresh_token=payload.refresh_token,
    )

    return {
        "access_token": new_access_token,
        "refresh_token": payload.refresh_token,
        "token_type": "bearer",
    }


@router.post("/logout", status_code=status.HTTP_200_OK)
def logout(payload: RefreshTokenRequest, db: Session = Depends(get_db)):
    auth_service.logout_user(db=db, refresh_token=payload.refresh_token)
    return {"message": "Logged out successfully"}


@router.get("/me", response_model=UserResponse)
def get_me(current_user=Depends(get_current_user)):
    return {
        "id": str(current_user.id),
        "email": str(current_user.email),
        "full_name": str(current_user.full_name) if current_user.full_name else None,
        "role": str(current_user.role),
        "token_balance": int(current_user.token_balance),
        "is_verified": bool(current_user.is_verified),
        "created_at": current_user.created_at,
    }