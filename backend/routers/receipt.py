from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from models.user import User
from models.cart import Cart
from models.cart_item import CartItem
from models.product import Product
from models.transaction import Transaction
from routers.users import get_current_user


router = APIRouter(
    prefix="/receipt",
    tags=["Receipt Intelligence"]
)


# ============================================================
# CUSTOMER RECEIPT
# ============================================================

@router.get("/{cart_id}")
def get_receipt(
    cart_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    cart = (
        db.query(Cart)
        .filter(
            Cart.id == cart_id,
            Cart.user_id == current_user.id,
            Cart.status == "COMPLETED"
        )
        .first()
    )

    if not cart:
        raise HTTPException(
            status_code=404,
            detail="Completed cart not found"
        )

    items = (
        db.query(CartItem, Product)
        .join(
            Product,
            CartItem.product_id == Product.id
        )
        .filter(
            CartItem.cart_id == cart.id
        )
        .all()
    )

    if not items:
        raise HTTPException(
            status_code=404,
            detail="No items found for this receipt"
        )

    # Find purchase transaction for this cart
    transaction = (
        db.query(Transaction)
        .filter(
            Transaction.user_id == current_user.id,
            Transaction.transaction_type == "PURCHASE",
            Transaction.description ==
            f"SmartPay shopping purchase - Cart #{cart.id}"
        )
        .order_by(Transaction.id.desc())
        .first()
    )

    if not transaction:
        raise HTTPException(
            status_code=404,
            detail="Purchase transaction not found"
        )

    receipt_code = f"SP-{transaction.id}-{cart.id}"

    receipt_items = []

    category_totals = {}

    total_quantity = 0

    for cart_item, product in items:

        subtotal = (
            Decimal(str(cart_item.quantity))
            * Decimal(str(cart_item.unit_price))
        )

        total_quantity += cart_item.quantity

        category = product.category

        if category not in category_totals:
            category_totals[category] = Decimal("0.00")

        category_totals[category] += subtotal

        receipt_items.append({
            "product_id": product.id,
            "name": product.name,
            "brand": product.brand,
            "category": product.category,
            "barcode": product.barcode,
            "quantity": cart_item.quantity,
            "unit_price": cart_item.unit_price,
            "subtotal": subtotal
        })

    return {
        "receipt": {
            "receipt_code": receipt_code,
            "cart_id": cart.id,
            "transaction_id": transaction.id,
            "status": "PAID",
            "items": receipt_items,
            "total_amount": cart.total_amount,
            "total_items": total_quantity,
            "category_breakdown": category_totals,
            "created_at": transaction.created_at
        }
    }


# ============================================================
# COUNTER VERIFICATION
# ============================================================

@router.get("/verify/{receipt_code}")
def verify_receipt(
    receipt_code: str,
    db: Session = Depends(get_db)
):
    """
    Counter scans the customer's SmartPay receipt barcode.

    Expected format:

        SP-{transaction_id}-{cart_id}

    Example:

        SP-8-7
    """

    parts = receipt_code.strip().upper().split("-")

    if len(parts) != 3 or parts[0] != "SP":
        raise HTTPException(
            status_code=400,
            detail="Invalid SmartPay receipt barcode"
        )

    try:
        transaction_id = int(parts[1])
        cart_id = int(parts[2])
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Invalid SmartPay receipt barcode"
        )

    transaction = (
        db.query(Transaction)
        .filter(
            Transaction.id == transaction_id,
            Transaction.transaction_type == "PURCHASE",
            Transaction.status == "SUCCESS"
        )
        .first()
    )

    if not transaction:
        raise HTTPException(
            status_code=404,
            detail="Valid SmartPay payment not found"
        )

    cart = (
        db.query(Cart)
        .filter(
            Cart.id == cart_id,
            Cart.user_id == transaction.user_id,
            Cart.status == "COMPLETED"
        )
        .first()
    )

    if not cart:
        raise HTTPException(
            status_code=404,
            detail="Completed SmartPay purchase not found"
        )

    expected_code = f"SP-{transaction.id}-{cart.id}"

    if receipt_code.strip().upper() != expected_code:
        raise HTTPException(
            status_code=400,
            detail="Receipt barcode verification failed"
        )

    items = (
        db.query(CartItem, Product)
        .join(
            Product,
            CartItem.product_id == Product.id
        )
        .filter(
            CartItem.cart_id == cart.id
        )
        .all()
    )

    verified_items = []

    total_quantity = 0

    for cart_item, product in items:

        subtotal = (
            Decimal(str(cart_item.quantity))
            * Decimal(str(cart_item.unit_price))
        )

        total_quantity += cart_item.quantity

        verified_items.append({
            "product_id": product.id,
            "name": product.name,
            "brand": product.brand,
            "barcode": product.barcode,
            "quantity": cart_item.quantity,
            "unit_price": cart_item.unit_price,
            "subtotal": subtotal
        })

    return {
        "verified": True,
        "message": "SmartPay payment verified successfully",
        "payment": {
            "receipt_code": expected_code,
            "transaction_id": transaction.id,
            "cart_id": cart.id,
            "status": "PAID",
            "amount": transaction.amount,
            "created_at": transaction.created_at
        },
        "purchase": {
            "total_items": total_quantity,
            "items": verified_items
        }
    }