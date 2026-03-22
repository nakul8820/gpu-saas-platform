from sqlalchemy.orm import Session
from sqlalchemy import text
from fastapi import HTTPException
import uuid

def get_all_packages(db:Session):
    """
    Fetche all active token packages from DB
    These were seeded when we ran the schema
    """
    result = db.execute(
        text("""
        SELECT id, name, token_amount, price_inr, bonus_tokens
        FROM token_packages
        WHERE is_active = true
        ORDER BY sort_order
        """)
    ).fetchall()
    return result

def get_user_balance(db: Session, user_id: str):
    """
    get balance + email for a user .
    read token balance from the user table
    for billing-critical ops we'd use get_user_balance() in postgres
    """
    result = db.execute(
        text("""
            SELECT token_balance, email
            FROM users
            WHERE id = :user_id
        """),
        {"user_id":user_id}
    ).fetchone()

    if not result:
        raise HTTPException(status_code= 404, detail="User not found")
    return result

def get_ledger_history(db: Session, user_id: str, page: int, page_size: int):
    offset = (page - 1) * page_size

    total = db.execute(
        text("SELECT COUNT(*) FROM token_ledger WHERE user_id = :uid"),
        {"uid": user_id}
    ).scalar()

    entries = db.execute(
        text("""
            SELECT id, amount, entry_type, balance_after, description, created_at
            FROM token_ledger
            WHERE user_id = :uid
            ORDER BY created_at DESC
            LIMIT :limit OFFSET :offset
        """),
        {"uid": user_id, "limit": page_size, "offset": offset}
    ).fetchall()

    return entries, total

    return entries, total

def add_tokens(db : Session, user_id: str, package_id: str):
    """
    Add tokens to user's account by :
    1. Look up the package to get token amount
    2. Get current balance
    3. Calculate new balance 
    4. Insert a ledger entry ( triggers update users.token_balance)
    5. Record a payment row
    """

    # Step 1 Get the package

    package = db.execute(
        text("""
            SELECT id, name, token_amount, bonus_tokens, price_inr
            FROM token_packages
            WHERE id = :pid AND is_active = true   
        """),
        {"pid": package_id}
    ).fetchone()

    if not package:
        raise HTTPException(status_code=404, detail="Package not found")

    total_tokens = package.token_amount + package.bonus_tokens

    # step 2 get current balance

    user = db.execute(
        text("SELECT token_balance FROM users WHERE id = :uid"),
        {"uid" : user_id}
    ).fetchone()

    # Step 3 Calculate balance after this credit
    new_balance = user.token_balance + total_tokens

    # Step 4 Insert Ledger entry
    ledger_id = str(uuid.uuid4())
    db.execute(
        text("""
            INSERT INTO token_ledger
                (id, user_id, amount, entry_type, balance_after,
                ref_package_id, description)
            VALUES
                (:id, :user_id, :amount, 'purchase', :balance_after,
                 :package_id, :description)
        """),
        {
            "id": ledger_id,
            "user_id" : user_id,
            "amount" : total_tokens,
            "balance_after" : new_balance,
            "package_id" : package_id,
            "description": f"Purchased {package.name} package - {total_tokens} tokens"
        }
    )

    # Step 5 Record a payment row ( manual )
    payment_id = str(uuid.uuid4())
    db.execute(
        text("""
            INSERT INTO payments
                (id, user_id, package_id, amount_inr,
                 tokens_credited, status, completed_at)
            VALUES
                (:id, :user_id, :package_id, :amount_inr,
                 :tokens_credited, 'succeeded', NOW())
        """),
        {
            "id" : payment_id,
            "user_id" : user_id,
            "package_id" : package_id,
            "amount_inr" : package.price_inr,
            "tokens_credited" : total_tokens
        }
    )

    db.commit()

    # Return updated balance 
    updated = db.execute(
        text("SELECT token_balance FROM users WHERE id= :uid"),
        {"uid": user_id}
    ).fetchone()

    return {
        "message" : f"Successfully added {total_tokens} tokens",
        "tokens_added": total_tokens,
        "new_balance": updated.token_balance,
        "package_name": package.name
    }