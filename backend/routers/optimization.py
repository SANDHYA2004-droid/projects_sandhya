from decimal import Decimal

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import get_db
from models.user import User
from models.budget import Budget
from models.cart import Cart
from models.cart_item import CartItem
from models.product import Product
from routers.users import get_current_user


router = APIRouter(
    prefix="/ai",
    tags=["AI Smart Cart"]
)


@router.get("/cart-analysis")
def analyze_cart(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # ---------------------------------------------------------
    # 1. GET USER BUDGET
    # ---------------------------------------------------------

    budget = (
        db.query(Budget)
        .filter(
            Budget.user_id == current_user.id
        )
        .first()
    )

    if not budget:
        return {
            "status": "BUDGET_NOT_SET",
            "message": "Please set a budget first."
        }

    # ---------------------------------------------------------
    # 2. GET ACTIVE CART
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
        return {
            "status": "EMPTY_CART",
            "message": "Your cart is empty."
        }

    # ---------------------------------------------------------
    # 3. GET CART ITEMS + PRODUCTS
    # ---------------------------------------------------------

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
        return {
            "status": "EMPTY_CART",
            "message": "Your cart is empty."
        }

    # ---------------------------------------------------------
    # 4. CALCULATE TOTAL AND BUDGET DIFFERENCE
    # ---------------------------------------------------------

    total = Decimal(str(cart.total_amount))
    budget_amount = Decimal(str(budget.amount))

    difference = budget_amount - total

    # ---------------------------------------------------------
    # 5. CART ITEM DETAILS
    # ---------------------------------------------------------

    cart_items = []

    for item, product in items:

        subtotal = Decimal(str(item.subtotal))

        cart_items.append({
            "cart_item_id": item.id,
            "product_id": product.id,
            "name": product.name,
            "category": product.category,
            "quantity": item.quantity,
            "unit_price": Decimal(str(item.unit_price)),
            "subtotal": subtotal
        })

    # ---------------------------------------------------------
    # 6. WITHIN BUDGET
    # ---------------------------------------------------------

    if difference >= 0:

        recommendations = [
            f"You have ₹{difference:.2f} remaining in your budget."
        ]

        return {
            "status": "WITHIN_BUDGET",
            "cart_total": total,
            "budget": budget_amount,
            "difference": difference,
            "recommendations": recommendations,
            "optimization": {
                "action": "NO_REMOVAL_REQUIRED",
                "message": "Your cart is within your budget."
            },
            "cart_items": cart_items
        }

    # ---------------------------------------------------------
    # 7. OVER BUDGET
    # ---------------------------------------------------------

    amount_over = abs(difference)

    recommendations = [
        f"You are ₹{amount_over:.2f} over your budget."
    ]

    # Sort items from most expensive to least expensive
    sorted_items = sorted(
        cart_items,
        key=lambda x: x["subtotal"],
        reverse=True
    )

    # ---------------------------------------------------------
    # 8. FIND SINGLE ITEM THAT CAN FIX THE BUDGET
    # ---------------------------------------------------------

    recommended_item = None

    for item in sorted_items:

        new_total = total - item["subtotal"]

        if new_total <= budget_amount:
            recommended_item = item
            break

    # ---------------------------------------------------------
    # 9. IF ONE ITEM IS ENOUGH
    # ---------------------------------------------------------

    if recommended_item:

        item = recommended_item

        new_total = total - item["subtotal"]
        remaining_budget = budget_amount - new_total

        recommendations.append(
            f"Consider removing {item['name']} "
            f"to bring your cart within budget."
        )

        recommendations.append(
            f"You would save ₹{item['subtotal']:.2f}."
        )

        recommendations.append(
            f"Your new cart total would be ₹{new_total:.2f}."
        )

        recommendations.append(
            f"You would have ₹{remaining_budget:.2f} remaining."
        )

        return {
            "status": "OVER_BUDGET",
            "cart_total": total,
            "budget": budget_amount,
            "difference": difference,
            "recommendations": recommendations,
            "optimization": {
                "action": "REMOVE_ITEM",
                "recommended_item": {
                    "cart_item_id": item["cart_item_id"],
                    "product_id": item["product_id"],
                    "name": item["name"],
                    "category": item["category"],
                    "quantity": item["quantity"],
                    "subtotal": item["subtotal"]
                },
                "savings": item["subtotal"],
                "new_cart_total": new_total,
                "remaining_budget": remaining_budget
            },
            "cart_items": cart_items
        }

    # ---------------------------------------------------------
    # 10. IF ONE ITEM IS NOT ENOUGH
    #     FIND TWO-ITEM COMBINATION
    # ---------------------------------------------------------

    best_combination = None

    for i in range(len(sorted_items)):

        for j in range(i + 1, len(sorted_items)):

            item1 = sorted_items[i]
            item2 = sorted_items[j]

            savings = (
                item1["subtotal"]
                + item2["subtotal"]
            )

            new_total = total - savings

            if new_total <= budget_amount:

                if (
                    best_combination is None
                    or savings < best_combination["savings"]
                ):
                    best_combination = {
                        "item1": item1,
                        "item2": item2,
                        "savings": savings,
                        "new_total": new_total
                    }

    # ---------------------------------------------------------
    # 11. TWO-ITEM OPTIMIZATION FOUND
    # ---------------------------------------------------------

    if best_combination:

        item1 = best_combination["item1"]
        item2 = best_combination["item2"]

        savings = best_combination["savings"]
        new_total = best_combination["new_total"]

        remaining_budget = budget_amount - new_total

        recommendations.append(
            f"Consider removing {item1['name']} "
            f"and {item2['name']}."
        )

        recommendations.append(
            f"You would save ₹{savings:.2f}."
        )

        recommendations.append(
            f"Your new cart total would be ₹{new_total:.2f}."
        )

        recommendations.append(
            f"You would have ₹{remaining_budget:.2f} remaining."
        )

        return {
            "status": "OVER_BUDGET",
            "cart_total": total,
            "budget": budget_amount,
            "difference": difference,
            "recommendations": recommendations,
            "optimization": {
                "action": "REMOVE_MULTIPLE_ITEMS",
                "recommended_items": [
                    {
                        "cart_item_id": item1["cart_item_id"],
                        "product_id": item1["product_id"],
                        "name": item1["name"],
                        "category": item1["category"],
                        "quantity": item1["quantity"],
                        "subtotal": item1["subtotal"]
                    },
                    {
                        "cart_item_id": item2["cart_item_id"],
                        "product_id": item2["product_id"],
                        "name": item2["name"],
                        "category": item2["category"],
                        "quantity": item2["quantity"],
                        "subtotal": item2["subtotal"]
                    }
                ],
                "savings": savings,
                "new_cart_total": new_total,
                "remaining_budget": remaining_budget
            },
            "cart_items": cart_items
        }

    # ---------------------------------------------------------
    # 12. NO SIMPLE OPTIMIZATION FOUND
    # ---------------------------------------------------------

    recommendations.append(
        "Your cart is significantly over budget. "
        "Consider reviewing multiple items before checkout."
    )

    return {
        "status": "OVER_BUDGET",
        "cart_total": total,
        "budget": budget_amount,
        "difference": difference,
        "recommendations": recommendations,
        "optimization": {
            "action": "REVIEW_MULTIPLE_ITEMS",
            "message": (
                "No single item or two-item combination "
                "was sufficient to bring the cart within budget."
            )
        },
        "cart_items": cart_items
    }