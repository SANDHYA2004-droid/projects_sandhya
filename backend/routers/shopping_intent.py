from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from models.user import User
from models.cart import Cart
from models.cart_item import CartItem
from models.product import Product
from routers.users import get_current_user


router = APIRouter(
    prefix="/shopping-intent",
    tags=["Shopping Intent"]
)


# ============================================================
# 1. DETECT SHOPPING INTENT
# ============================================================

@router.get("/{cart_id}")
def detect_shopping_intent(
    cart_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):

    # --------------------------------------------------------
    # Find cart belonging to current user
    # --------------------------------------------------------

    cart = (
        db.query(Cart)
        .filter(
            Cart.id == cart_id,
            Cart.user_id == current_user.id
        )
        .first()
    )

    if not cart:
        raise HTTPException(
            status_code=404,
            detail="Cart not found"
        )

    # --------------------------------------------------------
    # Intent detection should be performed only after checkout
    # --------------------------------------------------------

    if cart.status != "COMPLETED":
        raise HTTPException(
            status_code=400,
            detail={
                "message": "Shopping intent can be detected only for a completed cart.",
                "cart_id": cart.id,
                "cart_status": cart.status
            }
        )

    # --------------------------------------------------------
    # Get products purchased in the cart
    # --------------------------------------------------------

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
            detail="No items found in this cart"
        )

    # --------------------------------------------------------
    # Calculate category spending and quantity
    # --------------------------------------------------------

    category_spending = defaultdict(float)
    category_quantity = defaultdict(int)

    total_spending = 0.0
    total_items = 0

    for cart_item, product in items:

        quantity = cart_item.quantity
        unit_price = float(cart_item.unit_price)

        subtotal = quantity * unit_price

        category_spending[product.category] += subtotal
        category_quantity[product.category] += quantity

        total_spending += subtotal
        total_items += quantity

    # --------------------------------------------------------
    # Find dominant category
    # --------------------------------------------------------

    dominant_category = max(
        category_spending,
        key=category_spending.get
    )

    dominant_spending = category_spending[dominant_category]

    # --------------------------------------------------------
    # Calculate dominant category percentage
    # --------------------------------------------------------

    if total_spending > 0:
        dominant_percentage = (
            dominant_spending / total_spending
        ) * 100
    else:
        dominant_percentage = 0

    # --------------------------------------------------------
    # Rule-based shopping intent detection
    # --------------------------------------------------------

    if dominant_category == "Groceries":

        intent = "Grocery Restocking"
        confidence = 0.85

    elif dominant_category == "Snacks":

        intent = "Snack / Casual Shopping"
        confidence = 0.80

    elif dominant_category in [
        "Personal Care",
        "Beauty"
    ]:

        intent = "Personal Care Shopping"
        confidence = 0.85

    elif dominant_category in [
        "Electronics",
        "Accessories"
    ]:

        intent = "Electronics Shopping"
        confidence = 0.80

    elif dominant_category in [
        "Household",
        "Home"
    ]:

        intent = "Household Shopping"
        confidence = 0.80

    elif dominant_category in [
        "Clothing",
        "Fashion"
    ]:

        intent = "Clothing / Fashion"
        confidence = 0.80

    else:

        intent = "General Shopping"
        confidence = 0.60

    # --------------------------------------------------------
    # Return analysis
    # --------------------------------------------------------

    return {
        "status": "SUCCESS",

        "cart_id": cart.id,

        "shopping_intent": intent,

        "confidence": confidence,

        "dominant_category": dominant_category,

        "dominant_category_percentage": round(
            dominant_percentage,
            2
        ),

        "total_spending": round(
            total_spending,
            2
        ),

        "total_items": total_items,

        "category_spending": {
            category: round(
                amount,
                2
            )
            for category, amount
            in category_spending.items()
        },

        "category_quantity": dict(
            category_quantity
        ),

        "method": "Rule-based baseline"
    }


# ============================================================
# 2. CONFIRM SHOPPING INTENT
# ============================================================

@router.put("/{cart_id}/confirm")
def confirm_shopping_intent(
    cart_id: int,
    intent: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):

    # --------------------------------------------------------
    # Find cart
    # --------------------------------------------------------

    cart = (
        db.query(Cart)
        .filter(
            Cart.id == cart_id,
            Cart.user_id == current_user.id
        )
        .first()
    )

    if not cart:
        raise HTTPException(
            status_code=404,
            detail="Cart not found"
        )

    # --------------------------------------------------------
    # Intent confirmation only after checkout
    # --------------------------------------------------------

    if cart.status != "COMPLETED":
        raise HTTPException(
            status_code=400,
            detail={
                "message": "Shopping intent can be confirmed only for a completed cart.",
                "cart_id": cart.id,
                "cart_status": cart.status
            }
        )

    # --------------------------------------------------------
    # Allowed shopping intents
    # --------------------------------------------------------

    allowed_intents = [
        "Grocery Restocking",
        "Snack / Casual Shopping",
        "Personal Care Shopping",
        "Electronics Shopping",
        "Household Shopping",
        "Clothing / Fashion",
        "General Shopping"
    ]

    # --------------------------------------------------------
    # Validate intent
    # --------------------------------------------------------

    if intent not in allowed_intents:

        raise HTTPException(
            status_code=400,
            detail={
                "message": "Invalid shopping intent",
                "allowed_intents": allowed_intents
            }
        )

    # --------------------------------------------------------
    # Save user's confirmed intent
    # --------------------------------------------------------

    cart.shopping_intent = intent
    cart.intent_source = "USER"

    db.commit()
    db.refresh(cart)

    # --------------------------------------------------------
    # Return result
    # --------------------------------------------------------

    return {
        "status": "SUCCESS",

        "cart_id": cart.id,

        "shopping_intent": cart.shopping_intent,

        "intent_source": cart.intent_source,

        "message": "Shopping intent saved successfully"
    }