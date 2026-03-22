from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.core.database import get_db

router = APIRouter()

@router.get("/")
def root():
    return {"status": "GPU Platform API is running"}

@router.get("/health/db")
def check_db(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
        result = db.execute(text("SELECT COUNT(*) FROM users")).scalar()
        return {"database": "connected", "users_count": result}
    except Exception as e:
        return {"database": "error", "detail": str(e)}
