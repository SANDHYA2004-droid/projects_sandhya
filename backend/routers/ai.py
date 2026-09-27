from pathlib import Path

import joblib
import pandas as pd

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from models.transaction import Transaction
from models.user import User
from routers.users import get_current_user


# ============================================================
# ROUTER
# ============================================================

router = APIRouter(
    prefix="/ai",
    tags=["AI"]
)


# ============================================================
# MODEL PATH
# ============================================================

MODEL_PATH = (
    Path(__file__).resolve().parent.parent
    / "ml"
    / "spending_model.pkl"
)


# ============================================================
# LOAD ML MODEL
# ============================================================

def load_spending_model():

    if not MODEL_PATH.exists():
        raise HTTPException(
            status_code=503,
            detail=(
                "Spending ML model not found. "
                "Please train the model first."
            )
        )

    try:
        model_package = joblib.load(MODEL_PATH)

        # ----------------------------------------------------
        # Case 1: Model was saved directly
        # ----------------------------------------------------

        if hasattr(model_package, "predict"):
            return model_package

        # ----------------------------------------------------
        # Case 2: Model was saved inside a dictionary
        # ----------------------------------------------------

        if isinstance(model_package, dict):

            if "model" in model_package:
                model = model_package["model"]

                if hasattr(model, "predict"):
                    return model

            if "estimator" in model_package:
                model = model_package["estimator"]

                if hasattr(model, "predict"):
                    return model

        # ----------------------------------------------------
        # Invalid model
        # ----------------------------------------------------

        raise HTTPException(
            status_code=500,
            detail=(
                "The saved spending model has an invalid format. "
                "Please retrain the model."
            )
        )

    except HTTPException:
        raise

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=(
                f"Could not load spending ML model: {str(e)}"
            )
        )


# ============================================================
# GET DAILY SPENDING
# ============================================================

def get_daily_spending(
    db: Session,
    user_id: int
):

    transactions = (
        db.query(Transaction)
        .filter(
            # IMPORTANT:
            # Only retrieve transactions belonging
            # to the currently logged-in user.
            Transaction.user_id == user_id,

            Transaction.transaction_type == "PURCHASE",

            Transaction.status == "SUCCESS"
        )
        .order_by(
            Transaction.created_at.asc()
        )
        .all()
    )

    # --------------------------------------------------------
    # No transactions
    # --------------------------------------------------------

    if not transactions:
        return pd.DataFrame()

    records = []

    # --------------------------------------------------------
    # Convert transactions into records
    # --------------------------------------------------------

    for transaction in transactions:

        records.append(
            {
                "date": transaction.created_at.date(),
                "amount": float(transaction.amount)
            }
        )

    df = pd.DataFrame(records)

    # --------------------------------------------------------
    # Combine multiple purchases made on the same day
    # --------------------------------------------------------

    daily_spending = (
        df.groupby(
            "date",
            as_index=False
        )["amount"]
        .sum()
        .sort_values("date")
    )

    daily_spending.rename(
        columns={
            "amount": "daily_spending"
        },
        inplace=True
    )

    return daily_spending


# ============================================================
# CREATE FEATURES
# ============================================================

def create_prediction_features(
    df: pd.DataFrame
):

    df = df.copy()

    # Convert date to pandas datetime
    df["date"] = pd.to_datetime(
        df["date"]
    )

    # --------------------------------------------------------
    # Sequential day number
    # --------------------------------------------------------

    df["day_index"] = range(
        len(df)
    )

    # --------------------------------------------------------
    # Monday = 0 ... Sunday = 6
    # --------------------------------------------------------

    df["day_of_week"] = (
        df["date"].dt.dayofweek
    )

    # --------------------------------------------------------
    # Previous day's spending
    # --------------------------------------------------------

    df["lag_1"] = (
        df["daily_spending"]
        .shift(1)
    )

    # --------------------------------------------------------
    # Average spending of previous 3 days
    # --------------------------------------------------------

    df["rolling_mean_3"] = (
        df["daily_spending"]
        .shift(1)
        .rolling(
            window=3,
            min_periods=1
        )
        .mean()
    )

    return df


# ============================================================
# SPENDING PREDICTION
# ============================================================

@router.get("/spending-prediction")
def spending_prediction(
    current_user: User = Depends(
        get_current_user
    ),
    db: Session = Depends(
        get_db
    )
):

    # ========================================================
    # 1. LOAD TRAINED MODEL
    # ========================================================

    model = load_spending_model()

    # ========================================================
    # 2. GET CURRENT USER'S SPENDING HISTORY
    # ========================================================

    df = get_daily_spending(
        db,
        current_user.id
    )

    # ========================================================
    # 3. CHECK WHETHER USER HAS TRANSACTIONS
    # ========================================================

    if df.empty:

        raise HTTPException(
            status_code=404,
            detail=(
                "No successful purchase history found "
                "for this user."
            )
        )

    # ========================================================
    # 4. CHECK MINIMUM DATA
    # ========================================================

    if len(df) < 2:

        raise HTTPException(
            status_code=400,
            detail=(
                "Not enough spending history for prediction. "
                "At least 2 spending days are required."
            )
        )

    # ========================================================
    # 5. CREATE FEATURES
    # ========================================================

    feature_df = create_prediction_features(
        df
    )

    # ========================================================
    # 6. PREPARE NEXT-DAY PREDICTION
    # ========================================================

    last_date = feature_df[
        "date"
    ].max()

    next_date = (
        last_date
        + pd.Timedelta(days=1)
    )

    next_day_index = len(
        feature_df
    )

    next_day_of_week = (
        next_date.dayofweek
    )

    # ========================================================
    # 7. GET LAST SPENDING
    # ========================================================

    last_spending = float(
        feature_df[
            "daily_spending"
        ].iloc[-1]
    )

    # ========================================================
    # 8. CALCULATE RECENT 3-DAY AVERAGE
    # ========================================================

    previous_three_days = (
        feature_df[
            "daily_spending"
        ]
        .tail(3)
    )

    rolling_mean_3 = float(
        previous_three_days.mean()
    )

    # ========================================================
    # 9. CREATE PREDICTION INPUT
    # ========================================================

    X_prediction = pd.DataFrame(
        [
            {
                "day_index": next_day_index,

                "day_of_week": (
                    next_day_of_week
                ),

                "lag_1": (
                    last_spending
                ),

                "rolling_mean_3": (
                    rolling_mean_3
                )
            }
        ]
    )

    # ========================================================
    # 10. RUN ML PREDICTION
    # ========================================================

    try:

        prediction = model.predict(
            X_prediction
        )[0]

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=(
                "ML prediction failed. "
                "Model/features may be incompatible: "
                f"{str(e)}"
            )
        )

    # ========================================================
    # 11. CLEAN PREDICTION
    # ========================================================

    predicted_spending = max(
        0,
        float(prediction)
    )

    # ========================================================
    # 12. CALCULATE RECOMMENDED BUDGET
    # ========================================================

    # Add 10% safety margin

    recommended_budget = (
        predicted_spending * 1.10
    )

    # ========================================================
    # 13. DETERMINE SPENDING TREND
    # ========================================================

    if predicted_spending > rolling_mean_3:

        spending_trend = "increasing"

    elif predicted_spending < rolling_mean_3:

        spending_trend = "decreasing"

    else:

        spending_trend = "stable"

    # ========================================================
    # 14. RETURN RESPONSE
    # ========================================================

    return {

        "success": True,

        "user_id": current_user.id,

        "model": model.__class__.__name__,

        "prediction_date": (
            next_date.strftime(
                "%Y-%m-%d"
            )
        ),

        "predicted_spending": round(
            predicted_spending,
            2
        ),

        "recommended_budget": round(
            recommended_budget,
            2
        ),

        "last_spending": round(
            last_spending,
            2
        ),

        "average_recent_spending": round(
            rolling_mean_3,
            2
        ),

        "spending_days": len(
            df
        ),

        "spending_trend": (
            spending_trend
        ),

        "message": (
            "Spending prediction generated "
            "using the SmartPay AI ML model."
        )
    }