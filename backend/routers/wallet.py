from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from models.user import User
from models.wallet import Wallet
from models.transaction import Transaction
from routers.users import get_current_user


router = APIRouter(
    prefix="/wallet",
    tags=["Wallet"]
)


@router.post("/create")
def create_wallet(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    existing_wallet = (
        db.query(Wallet)
        .filter(Wallet.user_id == current_user.id)
        .first()
    )

    if existing_wallet:
        return {
            "message": "Wallet already exists",
            "wallet_id": existing_wallet.id,
            "balance": existing_wallet.balance
        }

    wallet = Wallet(
        user_id=current_user.id,
        balance=Decimal("0.00")
    )

    db.add(wallet)
    db.commit()
    db.refresh(wallet)

    return {
        "message": "Wallet created successfully",
        "wallet_id": wallet.id,
        "balance": wallet.balance
    }


@router.post("/add-money")
def add_money(
    amount: Decimal,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if amount <= 0:
        raise HTTPException(
            status_code=400,
            detail="Amount must be greater than zero"
        )

    wallet = (
        db.query(Wallet)
        .filter(Wallet.user_id == current_user.id)
        .first()
    )

    if not wallet:
        raise HTTPException(
            status_code=404,
            detail="Wallet not found. Create a wallet first."
        )

    wallet.balance += amount

    transaction = Transaction(
        user_id=current_user.id,
        transaction_type="ADD_MONEY",
        amount=amount,
        description="Wallet top-up"
    )

    db.add(transaction)
    db.commit()
    db.refresh(wallet)

    return {
        "message": "Money added successfully",
        "wallet_id": wallet.id,
        "balance": wallet.balance,
        "transaction_amount": amount
    }


@router.get("/balance")
def get_balance(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    wallet = (
        db.query(Wallet)
        .filter(Wallet.user_id == current_user.id)
        .first()
    )

    if not wallet:
        raise HTTPException(
            status_code=404,
            detail="Wallet not found"
        )

    return {
        "wallet_id": wallet.id,
        "balance": wallet.balance
    }


@router.get("/transactions")
def get_transactions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    transactions = (
        db.query(Transaction)
        .filter(Transaction.user_id == current_user.id)
        .order_by(Transaction.created_at.desc())
        .all()
    )

    return [
        {
            "id": transaction.id,
            "type": transaction.transaction_type,
            "amount": transaction.amount,
            "description": transaction.description,
            "created_at": transaction.created_at
        }
        for transaction in transactions
    ]