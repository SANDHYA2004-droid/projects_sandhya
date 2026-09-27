from collections import defaultdict
from decimal import Decimal

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import get_db

from models.user import User
from models.transaction import Transaction
from models.cart import Cart
from models.cart_item import CartItem
from models.product import Product
from models.wallet import Wallet

from routers.users import get_current_user
from ml.spending_model import predict_spending


router = APIRouter(
    prefix="/analytics",
    tags=["Analytics"]
)


# =========================================================
# HELPER
# =========================================================

def successful_purchase_transactions(
    current_user: User,
    db: Session
):
    """
    Returns only successful PURCHASE transactions
    belonging to the authenticated user.
    """

    return (
        db.query(Transaction)
        .filter(
            Transaction.user_id == current_user.id,
            Transaction.transaction_type == "PURCHASE",
            Transaction.status == "SUCCESS"
        )
        .order_by(
            Transaction.created_at.asc()
        )
        .all()
    )


# =========================================================
# SPENDING ANALYSIS
# =========================================================

@router.get("/spending")
def get_spending_analysis(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Returns spending analytics for the authenticated user.

    Only successful PURCHASE transactions are counted.
    Wallet top-ups are not counted as spending.
    """

    transactions = successful_purchase_transactions(
        current_user,
        db
    )

    total_spending = sum(
        (
            Decimal(str(t.amount))
            for t in transactions
        ),
        Decimal("0.00")
    )

    transaction_count = len(transactions)

    if transaction_count > 0:
        average_transaction = (
            total_spending /
            transaction_count
        )
    else:
        average_transaction = Decimal("0.00")

    # -----------------------------------------------------
    # WALLET
    # -----------------------------------------------------

    wallet = (
        db.query(Wallet)
        .filter(
            Wallet.user_id == current_user.id
        )
        .first()
    )

    wallet_balance = (
        Decimal(str(wallet.balance))
        if wallet
        else Decimal("0.00")
    )

    return {
        "status": "SUCCESS",

        "user_id": current_user.id,

        "total_spending": float(
            total_spending
        ),

        "transaction_count":
            transaction_count,

        "average_transaction": float(
            average_transaction
        ),

        "wallet_balance": float(
            wallet_balance
        ),

        "recommendation": (
            "Keep monitoring your SmartPay spending "
            "to receive personalized AI recommendations."
        )
    }


# =========================================================
# SPENDING HISTORY
# =========================================================

@router.get("/spending-history")
def get_spending_history(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Returns daily successful PURCHASE spending.

    This endpoint is designed for the frontend
    Spending Analytics visualization.

    Example:

    {
        "status": "SUCCESS",
        "user_id": 1,
        "history": [
            {
                "date": "2026-09-04",
                "amount": 260.0
            },
            {
                "date": "2026-09-05",
                "amount": 540.0
            }
        ]
    }
    """

    transactions = successful_purchase_transactions(
        current_user,
        db
    )

    daily_spending = defaultdict(float)

    for transaction in transactions:

        if not transaction.created_at:
            continue

        date_key = transaction.created_at.date().isoformat()

        amount = float(
            transaction.amount or 0
        )

        daily_spending[date_key] += amount

    history = [
        {
            "date": date,
            "amount": round(
                amount,
                2
            )
        }
        for date, amount
        in sorted(daily_spending.items())
    ]

    return {
        "status": "SUCCESS",
        "user_id": current_user.id,
        "history": history
    }


# =========================================================
# DASHBOARD SUMMARY
# =========================================================

@router.get("/dashboard")
def get_dashboard_analytics(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Returns the main values required by the
    SmartPay dashboard.

    Includes:

    - Wallet balance
    - Total spending
    - Transaction count
    - Active cart value
    - Active cart item count
    """

    # -----------------------------------------------------
    # WALLET
    # -----------------------------------------------------

    wallet = (
        db.query(Wallet)
        .filter(
            Wallet.user_id == current_user.id
        )
        .first()
    )

    wallet_balance = (
        Decimal(str(wallet.balance))
        if wallet
        else Decimal("0.00")
    )

    # -----------------------------------------------------
    # SPENDING
    # -----------------------------------------------------

    transactions = successful_purchase_transactions(
        current_user,
        db
    )

    total_spending = sum(
        (
            Decimal(str(t.amount))
            for t in transactions
        ),
        Decimal("0.00")
    )

    transaction_count = len(transactions)

    # -----------------------------------------------------
    # ACTIVE CART
    # -----------------------------------------------------

    active_cart = (
        db.query(Cart)
        .filter(
            Cart.user_id == current_user.id,
            Cart.status == "ACTIVE"
        )
        .order_by(
            Cart.created_at.desc()
        )
        .first()
    )

    cart_total = Decimal("0.00")
    cart_item_count = 0

    if active_cart:

        cart_total = Decimal(
            str(
                active_cart.total_amount or 0
            )
        )

        cart_items = (
            db.query(CartItem)
            .filter(
                CartItem.cart_id ==
                active_cart.id
            )
            .all()
        )

        cart_item_count = sum(
            int(item.quantity or 0)
            for item in cart_items
        )

    # -----------------------------------------------------
    # RESPONSE
    # -----------------------------------------------------

    return {
        "status": "SUCCESS",

        "user_id": current_user.id,

        "wallet": {
            "balance": float(
                wallet_balance
            ),

            "wallet_id": (
                wallet.id
                if wallet
                else None
            )
        },

        "spending": {
            "total": float(
                total_spending
            ),

            "transaction_count":
                transaction_count
        },

        "cart": {
            "id": (
                active_cart.id
                if active_cart
                else None
            ),

            "total": float(
                cart_total
            ),

            "item_count":
                cart_item_count,

            "status": (
                active_cart.status
                if active_cart
                else None
            )
        }
    }


# =========================================================
# AI SPENDING PREDICTION
# =========================================================

@router.get("/prediction")
def get_spending_prediction(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Generates an AI-based spending prediction for
    the currently authenticated SmartPay user.

    Only successful PURCHASE transactions belonging
    to the authenticated user are used.
    """

    prediction = predict_spending(
        db,
        current_user.id
    )

    return {
        "status": "SUCCESS",

        "user_id":
            current_user.id,

        "prediction":
            prediction
    }


# =========================================================
# REAL USER SHOPPING DATA
# =========================================================

@router.get("/training-data")
def get_training_data(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Converts the user's completed shopping carts
    into ML-ready data.

    Data comes directly from PostgreSQL.

    No manually created training data is required.
    """

    carts = (
        db.query(Cart)
        .filter(
            Cart.user_id == current_user.id,
            Cart.status == "COMPLETED"
        )
        .order_by(
            Cart.created_at.desc()
        )
        .all()
    )

    if not carts:

        return {
            "status":
                "INSUFFICIENT_DATA",

            "message":
                "No completed shopping sessions found.",

            "training_records": []
        }

    training_records = []

    for cart in carts:

        items = (
            db.query(
                CartItem,
                Product
            )
            .join(
                Product,
                CartItem.product_id ==
                Product.id
            )
            .filter(
                CartItem.cart_id ==
                cart.id
            )
            .all()
        )

        if not items:
            continue

        category_spending = defaultdict(float)
        category_quantity = defaultdict(int)

        total_items = 0
        total_item_price = 0.0

        for cart_item, product in items:

            quantity = int(
                cart_item.quantity or 0
            )

            unit_price = float(
                cart_item.unit_price or 0
            )

            subtotal = (
                quantity *
                unit_price
            )

            total_items += quantity

            total_item_price += subtotal

            category_spending[
                product.category
            ] += subtotal

            category_quantity[
                product.category
            ] += quantity

        if not category_spending:
            continue

        dominant_category = max(
            category_spending,
            key=category_spending.get
        )

        total_amount = float(
            cart.total_amount or 0
        )

        dominant_percentage = (
            category_spending[
                dominant_category
            ]
            / total_amount
            * 100
            if total_amount > 0
            else 0
        )

        average_item_price = (
            total_amount /
            total_items
            if total_items > 0
            else 0
        )

        training_records.append({

            "cart_id":
                cart.id,

            "total_amount":
                round(
                    total_amount,
                    2
                ),

            "total_items":
                total_items,

            "category_count":
                len(category_spending),

            "dominant_category":
                dominant_category,

            "dominant_category_percentage":
                round(
                    dominant_percentage,
                    2
                ),

            "average_item_price":
                round(
                    average_item_price,
                    2
                ),

            "category_spending":
                dict(category_spending),

            "category_quantity":
                dict(category_quantity),

            "shopping_intent":
                cart.shopping_intent,

            "intent_source":
                cart.intent_source
        })

    return {

        "status":
            "SUCCESS",

        "user_id":
            current_user.id,

        "shopping_sessions_analyzed":
            len(training_records),

        "training_records":
            training_records
    }


# =========================================================
# ML DATASET
# =========================================================

@router.get("/ml-dataset")
def get_ml_dataset(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Converts REAL USER shopping history into
    structured numerical features suitable
    for machine-learning models.

    No manually created training data is used.
    """

    carts = (
        db.query(Cart)
        .filter(
            Cart.user_id == current_user.id,
            Cart.status == "COMPLETED"
        )
        .order_by(
            Cart.created_at.asc()
        )
        .all()
    )

    if not carts:

        return {
            "status":
                "INSUFFICIENT_DATA",

            "message":
                "Not enough completed shopping history.",

            "dataset": []
        }

    dataset = []

    for cart in carts:

        items = (
            db.query(
                CartItem,
                Product
            )
            .join(
                Product,
                CartItem.product_id ==
                Product.id
            )
            .filter(
                CartItem.cart_id ==
                cart.id
            )
            .all()
        )

        if not items:
            continue

        category_spending = defaultdict(float)
        category_quantity = defaultdict(int)

        total_items = 0

        total_amount = float(
            cart.total_amount or 0
        )

        for cart_item, product in items:

            quantity = int(
                cart_item.quantity or 0
            )

            unit_price = float(
                cart_item.unit_price or 0
            )

            subtotal = (
                quantity *
                unit_price
            )

            total_items += quantity

            category_spending[
                product.category
            ] += subtotal

            category_quantity[
                product.category
            ] += quantity

        if total_items == 0:
            continue

        if not category_spending:
            continue

        dominant_category = max(
            category_spending,
            key=category_spending.get
        )

        dominant_percentage = (
            category_spending[
                dominant_category
            ]
            / total_amount
            * 100
            if total_amount > 0
            else 0
        )

        average_item_price = (
            total_amount /
            total_items
        )

        # -------------------------------------------------
        # CATEGORY SPENDING
        # -------------------------------------------------

        groceries_spending = (
            category_spending.get(
                "Groceries",
                0.0
            )
        )

        snacks_spending = (
            category_spending.get(
                "Snacks",
                0.0
            )
        )

        personal_care_spending = (
            category_spending.get(
                "Personal Care",
                0.0
            )
        )

        beauty_spending = (
            category_spending.get(
                "Beauty",
                0.0
            )
        )

        electronics_spending = (
            category_spending.get(
                "Electronics",
                0.0
            )
        )

        accessories_spending = (
            category_spending.get(
                "Accessories",
                0.0
            )
        )

        # -------------------------------------------------
        # DATASET RECORD
        # -------------------------------------------------

        dataset.append({

            "cart_id":
                cart.id,

            "total_amount":
                round(
                    total_amount,
                    2
                ),

            "total_items":
                total_items,

            "category_count":
                len(category_spending),

            "average_item_price":
                round(
                    average_item_price,
                    2
                ),

            "dominant_category_percentage":
                round(
                    dominant_percentage,
                    2
                ),

            "groceries_spending":
                round(
                    groceries_spending,
                    2
                ),

            "snacks_spending":
                round(
                    snacks_spending,
                    2
                ),

            "personal_care_spending":
                round(
                    personal_care_spending,
                    2
                ),

            "beauty_spending":
                round(
                    beauty_spending,
                    2
                ),

            "electronics_spending":
                round(
                    electronics_spending,
                    2
                ),

            "accessories_spending":
                round(
                    accessories_spending,
                    2
                ),

            "groceries_quantity":
                category_quantity.get(
                    "Groceries",
                    0
                ),

            "snacks_quantity":
                category_quantity.get(
                    "Snacks",
                    0
                ),

            "personal_care_quantity":
                category_quantity.get(
                    "Personal Care",
                    0
                ),

            "beauty_quantity":
                category_quantity.get(
                    "Beauty",
                    0
                ),

            "electronics_quantity":
                category_quantity.get(
                    "Electronics",
                    0
                ),

            "accessories_quantity":
                category_quantity.get(
                    "Accessories",
                    0
                ),

            "dominant_category":
                dominant_category,

            "shopping_intent":
                cart.shopping_intent,

            "intent_source":
                cart.intent_source
        })

    return {

        "status":
            "SUCCESS",

        "user_id":
            current_user.id,

        "records":
            len(dataset),

        "features": [

            "total_amount",

            "total_items",

            "category_count",

            "average_item_price",

            "dominant_category_percentage",

            "groceries_spending",

            "snacks_spending",

            "personal_care_spending",

            "beauty_spending",

            "electronics_spending",

            "accessories_spending",

            "groceries_quantity",

            "snacks_quantity",

            "personal_care_quantity",

            "beauty_quantity",

            "electronics_quantity",

            "accessories_quantity",

            "dominant_category",

            "shopping_intent"
        ],

        "dataset":
            dataset
    }


# =========================================================
# AI SPENDING PREDICTION - ALIAS
# =========================================================

# =========================================================
# COMPLETE SPENDING HISTORY
# =========================================================

@router.get("/spending-history")
def get_spending_history(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Returns ALL successful PURCHASE transactions
    belonging to the currently authenticated user.

    No date limit.
    No recent-days limit.
    No pagination.
    No transaction limit.

    Used by the SmartPay Spending Analytics page.
    """

    transactions = (
        db.query(Transaction)
        .filter(
            Transaction.user_id == current_user.id,
            Transaction.transaction_type == "PURCHASE",
            Transaction.status == "SUCCESS"
        )
        .order_by(
            Transaction.created_at.asc()
        )
        .all()
    )

    # -----------------------------------------------------
    # GROUP ALL PURCHASES BY DATE
    # -----------------------------------------------------

    daily_spending = defaultdict(Decimal)

    for transaction in transactions:

        if not transaction.created_at:
            continue

        transaction_date = (
            transaction.created_at.date()
        )

        amount = Decimal(
            str(transaction.amount or 0)
        )

        daily_spending[
            transaction_date
        ] += amount

    # -----------------------------------------------------
    # CREATE COMPLETE HISTORY
    # -----------------------------------------------------

    history = []

    for spending_date in sorted(
        daily_spending.keys()
    ):

        history.append({
            "date": spending_date.isoformat(),
            "amount": round(
                float(
                    daily_spending[
                        spending_date
                    ]
                ),
                2
            )
        })

    # -----------------------------------------------------
    # TOTAL
    # -----------------------------------------------------

    total_spending = sum(
        (
            Decimal(
                str(item["amount"])
            )
            for item in history
        ),
        Decimal("0.00")
    )

    # -----------------------------------------------------
    # RESPONSE
    # -----------------------------------------------------

    return {
        "status": "SUCCESS",
        "user_id": current_user.id,

        "total_spending": round(
            float(total_spending),
            2
        ),

        "spending_days": len(history),

        "history": history
    }