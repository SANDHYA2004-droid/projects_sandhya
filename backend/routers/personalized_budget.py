from decimal import Decimal

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import get_db
from models.user import User
from models.cart import Cart
from models.cart_item import CartItem
from models.product import Product
from routers.users import get_current_user


router = APIRouter(
    prefix="/ai",
    tags=["AI Personalized Budget"]
)


@router.get("/recommended-budget")
def recommended_budget(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # --------------------------------------------------
    # Get completed shopping carts
    # --------------------------------------------------

    completed_carts = (
        db.query(Cart)
        .filter(
            Cart.user_id == current_user.id,
            Cart.status == "COMPLETED"
        )
        .order_by(Cart.created_at.asc())
        .all()
    )

    if not completed_carts:
        return {
            "status": "INSUFFICIENT_DATA",
            "message": (
                "Not enough completed shopping history "
                "to generate a personalized budget."
            ),
            "recommended_budget": None
        }

    # --------------------------------------------------
    # Get all items from completed carts
    # --------------------------------------------------

    cart_ids = [cart.id for cart in completed_carts]

    shopping_items = (
        db.query(CartItem, Product)
        .join(
            Product,
            CartItem.product_id == Product.id
        )
        .filter(
            CartItem.cart_id.in_(cart_ids)
        )
        .all()
    )

    if not shopping_items:
        return {
            "status": "INSUFFICIENT_DATA",
            "message": "Completed carts contain no products.",
            "recommended_budget": None
        }

    # --------------------------------------------------
    # Calculate total spending
    # --------------------------------------------------

    total_spending = Decimal("0.00")

    category_spending = {}

    total_items = 0

    for cart_item, product in shopping_items:

        subtotal = Decimal(str(cart_item.subtotal))

        total_spending += subtotal

        total_items += cart_item.quantity

        category = product.category

        if category not in category_spending:
            category_spending[category] = Decimal("0.00")

        category_spending[category] += subtotal

    # --------------------------------------------------
    # Number of completed shopping transactions
    # --------------------------------------------------

    transaction_count = len(completed_carts)

    # --------------------------------------------------
    # Average transaction
    # --------------------------------------------------

    average_transaction = (
        total_spending /
        Decimal(str(transaction_count))
    )

    # --------------------------------------------------
    # Determine spending period
    # --------------------------------------------------

    first_date = completed_carts[0].created_at
    last_date = completed_carts[-1].created_at

    days_analyzed = (
        last_date - first_date
    ).days + 1

    if days_analyzed < 1:
        days_analyzed = 1

    # --------------------------------------------------
    # Average daily spending
    # --------------------------------------------------

    average_daily_spending = (
        total_spending /
        Decimal(str(days_analyzed))
    )

    # --------------------------------------------------
    # Project spending for 30 days
    # --------------------------------------------------

    projected_monthly_spending = (
        average_daily_spending *
        Decimal("30")
    )

    # --------------------------------------------------
    # Add 10% safety buffer
    # --------------------------------------------------

    recommended_budget = (
        projected_monthly_spending *
        Decimal("1.10")
    )

    # --------------------------------------------------
    # Calculate category percentages
    # --------------------------------------------------

    category_breakdown = {}

    for category, amount in category_spending.items():

        percentage = (
            amount /
            total_spending
        ) * Decimal("100")

        category_breakdown[category] = {
            "spent": amount.quantize(
                Decimal("0.01")
            ),
            "percentage": percentage.quantize(
                Decimal("0.01")
            )
        }

    # --------------------------------------------------
    # Calculate recommended category budgets
    # --------------------------------------------------

    category_budgets = {}

    for category, data in category_breakdown.items():

        percentage = data["percentage"]

        allocation = (
            recommended_budget *
            percentage /
            Decimal("100")
        )

        category_budgets[category] = allocation.quantize(
            Decimal("0.01")
        )

    # --------------------------------------------------
    # Quantize decimal values
    # --------------------------------------------------

    total_spending = total_spending.quantize(
        Decimal("0.01")
    )

    average_transaction = average_transaction.quantize(
        Decimal("0.01")
    )

    average_daily_spending = average_daily_spending.quantize(
        Decimal("0.01")
    )

    projected_monthly_spending = (
        projected_monthly_spending.quantize(
            Decimal("0.01")
        )
    )

    recommended_budget = recommended_budget.quantize(
        Decimal("0.01")
    )

    # --------------------------------------------------
    # Return personalized budget
    # --------------------------------------------------

    return {
        "status": "SUCCESS",

        "shopping_carts_analyzed": transaction_count,

        "total_items": total_items,

        "total_spending": total_spending,

        "average_transaction": average_transaction,

        "days_analyzed": days_analyzed,

        "average_daily_spending": average_daily_spending,

        "projected_monthly_spending":
            projected_monthly_spending,

        "recommended_budget":
            recommended_budget,

        "safety_buffer_percent": 10,

        "category_spending":
            category_breakdown,

        "category_budgets":
            category_budgets,

        "method":
            "Category-aware spending projection"
    }