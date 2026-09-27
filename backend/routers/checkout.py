from decimal import Decimal
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from models.user import User
from models.cart import Cart
from models.cart_item import CartItem
from models.wallet import Wallet
from models.transaction import Transaction
from routers.users import get_current_user


router = APIRouter(
    prefix="/checkout",
    tags=["Checkout"]
)


@router.post("/")
def checkout(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # ---------------------------------------------------------
    # 1. FIND ACTIVE CART
    # ---------------------------------------------------------

    cart = (
        db.query(Cart)
        .filter(
            Cart.user_id == current_user.id,
            Cart.status == "ACTIVE"
        )
        .first()
    )

    if not cart:
        raise HTTPException(
            status_code=404,
            detail="Active cart not found"
        )

    # ---------------------------------------------------------
    # 2. GET CART ITEMS
    # ---------------------------------------------------------

    items = (
        db.query(CartItem)
        .filter(
            CartItem.cart_id == cart.id
        )
        .all()
    )

    if not items:
        raise HTTPException(
            status_code=400,
            detail="Cart is empty"
        )

    # ---------------------------------------------------------
    # 3. CALCULATE CART TOTAL
    # ---------------------------------------------------------

    cart_total = Decimal(
        str(cart.total_amount)
    )

    if cart_total <= 0:
        raise HTTPException(
            status_code=400,
            detail="Cart total must be greater than zero"
        )

    # ---------------------------------------------------------
    # 4. FIND USER WALLET
    # ---------------------------------------------------------

    wallet = (
        db.query(Wallet)
        .filter(
            Wallet.user_id == current_user.id
        )
        .first()
    )

    if not wallet:
        raise HTTPException(
            status_code=404,
            detail="Wallet not found"
        )

    wallet_balance = Decimal(
        str(wallet.balance)
    )

    # ---------------------------------------------------------
    # 5. CHECK WALLET BALANCE
    # ---------------------------------------------------------

    if wallet_balance < cart_total:
        raise HTTPException(
            status_code=400,
            detail={
                "message": "Insufficient wallet balance",
                "wallet_balance": float(wallet_balance),
                "cart_total": float(cart_total),
                "required": float(
                    cart_total - wallet_balance
                )
            }
        )

    # ---------------------------------------------------------
    # 6. GENERATE UNIQUE RECEIPT CODE
    # ---------------------------------------------------------

    receipt_code = (
        f"SP-{uuid.uuid4().hex[:12].upper()}"
    )

    # ---------------------------------------------------------
    # 7. DEDUCT MONEY FROM WALLET
    # ---------------------------------------------------------

    previous_balance = wallet_balance

    wallet.balance = (
        wallet_balance - cart_total
    )

    # ---------------------------------------------------------
    # 8. CREATE PURCHASE TRANSACTION
    # ---------------------------------------------------------

    transaction = Transaction(
        user_id=current_user.id,
        amount=cart_total,
        transaction_type="PURCHASE",
        status="SUCCESS",
        receipt_code=receipt_code,
        description=(
            f"SmartPay shopping purchase - "
            f"Cart #{cart.id}"
        )
    )

    db.add(transaction)

    # ---------------------------------------------------------
    # 9. COMPLETE CART
    # ---------------------------------------------------------

    cart.status = "COMPLETED"

    # ---------------------------------------------------------
    # 10. SAVE EVERYTHING
    # ---------------------------------------------------------

    db.commit()

    db.refresh(transaction)
    db.refresh(wallet)
    db.refresh(cart)

    # ---------------------------------------------------------
    # 11. RETURN PAYMENT RESULT
    # ---------------------------------------------------------

    return {
        "message": "Payment successful",

        "transaction": {
            "id": transaction.id,
            "amount": transaction.amount,
            "type": transaction.transaction_type,
            "status": transaction.status,
            "receipt_code": transaction.receipt_code,
            "description": transaction.description,
            "created_at": transaction.created_at
        },

        "wallet": {
            "previous_balance": previous_balance,
            "remaining_balance": wallet.balance
        },

        "cart": {
            "id": cart.id,
            "status": cart.status
        }
    }