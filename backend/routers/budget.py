from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from database import get_db
from models.user import User
from models.budget import Budget
from routers.users import get_current_user
from ml.spending_model import predict_spending


router = APIRouter(
    prefix="/budget",
    tags=["Budget"]
)


class BudgetCreate(BaseModel):
    amount: Decimal = Field(
        gt=0,
        decimal_places=2
    )


@router.post("/")
def save_budget(
    budget_data: BudgetCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Saves a SmartPay budget for the authenticated user.
    """

    prediction = predict_spending(
        db,
        current_user.id
    )

    predicted_spending = Decimal(
        str(
            prediction.get(
                "predicted_spending",
                0
            )
        )
    )

    budget_amount = Decimal(
        str(budget_data.amount)
    )

    safety_buffer = (
        budget_amount -
        predicted_spending
    )

    if safety_buffer < 0:
        safety_buffer = Decimal("0.00")

    budget = Budget(
        user_id=current_user.id,
        amount=budget_amount,
        predicted_spending=predicted_spending,
        safety_buffer=safety_buffer
    )

    db.add(budget)
    db.commit()
    db.refresh(budget)

    return {
        "status": "SUCCESS",
        "message": "Smart Budget saved successfully.",
        "budget": {
            "id": budget.id,
            "user_id": budget.user_id,
            "amount": float(budget.amount),
            "predicted_spending": float(
                budget.predicted_spending
            ),
            "safety_buffer": float(
                budget.safety_buffer
            ),
            "created_at": budget.created_at
        }
    }


@router.get("/")
def get_current_budget(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Returns the latest Smart Budget
    belonging only to the authenticated user.
    """

    budget = (
        db.query(Budget)
        .filter(
            Budget.user_id == current_user.id
        )
        .order_by(
            Budget.created_at.desc()
        )
        .first()
    )

    if not budget:
        return {
            "status": "NO_BUDGET",
            "message": "No Smart Budget has been saved yet."
        }

    return {
        "status": "SUCCESS",
        "budget": {
            "id": budget.id,
            "user_id": budget.user_id,
            "amount": float(budget.amount),
            "predicted_spending": float(
                budget.predicted_spending
            ),
            "safety_buffer": float(
                budget.safety_buffer
            ),
            "created_at": budget.created_at
        }
    }