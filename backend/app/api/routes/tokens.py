from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.schemas import (
    TokenPackageResponse,
    BalanceResponse,
    LedgerHistoryResponse,
    ManualTopUpRequest
)

from app.services import token_service

router = APIRouter(prefix="/tokens", tags=["Tokens"])

@router.get("/packages")
def list_packages(db: Session = Depends(get_db)):
    """
    Public facing endpoint - no auth required.
    Anyone can see available token packages.
    """
    packages = token_service.get_all_packages(db)
    return [
        {
            "id" : str(p.id),
            "name" : p.name,
            "token_amount" : p.token_amount,
            "price_inr" : float(p.price_inr),
            "bonus_tokens" : p.bonus_tokens,
            "total_tokens" : p.token_amount + p.bonus_tokens,
        }
        for p in packages
    ]

@router.get("/balance")
def get_balance(
    current_user=Depends(get_current_user), # JWT requires
    db: Session = Depends(get_db)
):
    """
    Protected- must be logged in
    Returns current token balances
    """
    result = token_service.get_user_balance(db, str(current_user.id))
    return {
        "balance": result.token_balance,
        "email": result.email,
    }

@router.get("/history")
def get_history(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, le=50),
    current_user=Depends(get_current_user),
    db:Session = Depends(get_db)
):
    """
    Protected - pagination transaction history.
    """ 
    entries, total = token_service.get_ledger_history(
        db, str(current_user.id), page, page_size
    )
    return {
        "entries" : [
            {
                "id":str(e.id),
                "amount":e.amount,
                "entry_type":e.entry_type,
                "balance_after":e.balance_after,
                "description":e.description,
                "created_at":e.created_at,
            }
            for e in entries
        ],
        "total":total,
        "page":page,
        "page_size": page_size,
    }

@router.post("/purchase")
def purchase_tokens(
    payload: ManualTopUpRequest,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Protected — buy a token package.
    For now this is a manual top-up (no real payment).
    Later we'll replace this with Stripe checkout.
    """
    result = token_service.add_tokens(
        db=db,
        user_id=str(current_user.id),
        package_id=payload.package_id,
    )
    return result