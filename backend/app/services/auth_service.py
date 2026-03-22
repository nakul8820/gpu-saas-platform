from sqlalchemy.orm import Session
from sqlalchemy import text
from fastapi import HTTPException, status
from datetime import datetime
import uuid

from app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_token,
)


def get_user_by_email(db: Session, email: str):
    result = db.execute(
        text("SELECT * FROM users WHERE LOWER(email) = LOWER(:email)"),
        {"email": email}
    ).fetchone()
    return result


def get_user_by_id(db: Session, user_id: str):
    result = db.execute(
        text("SELECT * FROM users WHERE id = :id"),
        {"id": user_id}
    ).fetchone()
    return result


def register_user(db: Session, email: str, password: str, full_name: str = None):
    # Check if email already exists
    existing = get_user_by_email(db, email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists"
        )

    hashed = hash_password(password)
    user_id = str(uuid.uuid4())

    db.execute(
        text("""
            INSERT INTO users (id, email, hashed_password, full_name, role, token_balance, is_verified)
            VALUES (:id, :email, :hashed_password, :full_name, 'user', 0, false)
        """),
        {
            "id": user_id,
            "email": email.lower(),
            "hashed_password": hashed,
            "full_name": full_name,
        }
    )
    db.commit()

    user = get_user_by_id(db, user_id)

    access_token = create_access_token({"sub": user_id, "email": email})
    refresh_token = create_refresh_token({"sub": user_id})

    # Store refresh token in user_sessions
    session_id = str(uuid.uuid4())
    db.execute(
        text("""
            INSERT INTO user_sessions (id, user_id, refresh_token, expires_at)
            VALUES (:id, :user_id, :refresh_token,
                    NOW() + INTERVAL '7 days')
        """),
        {
            "id": session_id,
            "user_id": user_id,
            "refresh_token": refresh_token,
        }
    )
    db.commit()

    return user, access_token, refresh_token


def login_user(db: Session, email: str, password: str):
    user = get_user_by_email(db, email)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )

    if not verify_password(password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account has been deactivated"
        )

    # Update last login
    db.execute(
        text("UPDATE users SET last_login_at = NOW() WHERE id = :id"),
        {"id": str(user.id)}
    )

    access_token = create_access_token({"sub": str(user.id), "email": user.email})
    refresh_token = create_refresh_token({"sub": str(user.id)})

    # Store new session
    session_id = str(uuid.uuid4())
    db.execute(
        text("""
            INSERT INTO user_sessions (id, user_id, refresh_token, expires_at)
            VALUES (:id, :user_id, :refresh_token,
                    NOW() + INTERVAL '7 days')
        """),
        {
            "id": session_id,
            "user_id": str(user.id),
            "refresh_token": refresh_token,
        }
    )
    db.commit()

    return user, access_token, refresh_token


def refresh_access_token(db: Session, refresh_token: str):
    payload = decode_token(refresh_token)

    if not payload or payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token"
        )

    # Check token exists in DB and is not revoked
    session = db.execute(
        text("""
            SELECT * FROM user_sessions
            WHERE refresh_token = :token
            AND revoked_at IS NULL
            AND expires_at > NOW()
        """),
        {"token": refresh_token}
    ).fetchone()

    if not session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token has been revoked or expired"
        )

    user_id = payload.get("sub")
    user = get_user_by_id(db, user_id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    new_access_token = create_access_token({"sub": user_id, "email": user.email})
    return new_access_token


def logout_user(db: Session, refresh_token: str):
    db.execute(
        text("""
            UPDATE user_sessions
            SET revoked_at = NOW()
            WHERE refresh_token = :token
        """),
        {"token": refresh_token}
    )
    db.commit()
