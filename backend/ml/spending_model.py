from pathlib import Path

import joblib
import pandas as pd
from sqlalchemy.orm import Session

from models.transaction import Transaction


# ============================================================
# MODEL PATH
# ============================================================

MODEL_PATH = (
    Path(__file__).resolve().parent
    / "spending_model.pkl"
)


# ============================================================
# LOAD TRAINED MODEL
# ============================================================

def load_model():
    """
    Loads the trained SmartPay spending model.
    """

    if not MODEL_PATH.exists():
        raise FileNotFoundError(
            f"ML model not found at {MODEL_PATH}. "
            "Run: python -m ml.train_spending_model"
        )

    return joblib.load(MODEL_PATH)


# ============================================================
# GET DAILY SPENDING FOR CURRENT USER
# ============================================================

def get_daily_spending(
    db: Session,
    user_id: int
):
    """
    Gets successful purchase transactions belonging
    only to the specified SmartPay user.

    Purchases made on the same calendar day are combined.

    Only successful PURCHASE transactions are included.
    """

    transactions = (
        db.query(Transaction)
        .filter(
            Transaction.user_id == user_id,
            Transaction.transaction_type == "PURCHASE",
            Transaction.status == "SUCCESS"
        )
        .order_by(
            Transaction.created_at.asc()
        )
        .all()
    )

    if not transactions:
        return pd.DataFrame(
            columns=[
                "date",
                "daily_spending"
            ]
        )

    records = []

    for transaction in transactions:

        records.append(
            {
                "date": transaction.created_at.date(),
                "amount": float(transaction.amount)
            }
        )

    df = pd.DataFrame(records)

    # --------------------------------------------------------
    # Combine transactions made on the same date
    # --------------------------------------------------------

    daily_spending = (
        df.groupby(
            "date",
            as_index=False
        )["amount"]
        .sum()
        .sort_values("date")
        .reset_index(drop=True)
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

def create_prediction_features(df):
    """
    Creates the same feature structure used during training.

    Features:
        - day_index
        - day_of_week
        - lag_1
        - rolling_mean_3
    """

    df = df.copy()

    if df.empty:
        return df

    # --------------------------------------------------------
    # Convert date
    # --------------------------------------------------------

    df["date"] = pd.to_datetime(
        df["date"]
    )

    # --------------------------------------------------------
    # Chronological spending observation index
    # --------------------------------------------------------

    df["day_index"] = range(
        len(df)
    )

    # --------------------------------------------------------
    # Monday = 0
    # Sunday = 6
    # --------------------------------------------------------

    df["day_of_week"] = (
        df["date"].dt.dayofweek
    )

    # --------------------------------------------------------
    # Previous spending observation
    # --------------------------------------------------------

    df["lag_1"] = (
        df["daily_spending"]
        .shift(1)
    )

    # --------------------------------------------------------
    # Previous 3 spending observations
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
# PREDICT NEXT SPENDING
# ============================================================

def predict_spending(
    db: Session,
    user_id: int
):
    """
    Predicts the next spending amount for the
    currently authenticated SmartPay user.

    Prediction uses only that user's successful
    purchase transaction history.

    The prediction considers:
        - previous spending
        - recent spending average
        - day of week
        - chronological spending history

    A recent-spending fallback is used if the trained
    model produces a zero prediction while actual
    recent spending exists.
    """

    # ========================================================
    # 1. LOAD MODEL
    # ========================================================

    model_bundle = load_model()

    model = model_bundle["model"]

    # --------------------------------------------------------
    # Support both old and corrected model packages
    # --------------------------------------------------------

    feature_columns = model_bundle.get(
        "feature_columns",
        model_bundle.get(
            "features",
            [
                "day_index",
                "day_of_week",
                "lag_1",
                "rolling_mean_3"
            ]
        )
    )

    model_type = model_bundle.get(
        "model_type",
        type(model).__name__
    )

    # ========================================================
    # 2. GET CURRENT USER'S REAL SPENDING DATA
    # ========================================================

    df = get_daily_spending(
        db,
        user_id
    )

    # ========================================================
    # 3. HANDLE NO SPENDING HISTORY
    # ========================================================

    if df.empty:

        return {
            "predicted_spending": 0.00,
            "recommended_budget": 0.00,
            "last_daily_spending": 0.00,
            "recent_average_spending": 0.00,
            "last_spending_date": None,
            "next_prediction_date": None,
            "spending_days": 0,
            "model_type": model_type,
            "prediction_source": "no_history",
            "message": (
                "No successful purchase history "
                "is available for this user."
            )
        }

    # ========================================================
    # 4. CREATE FEATURES
    # ========================================================

    df = create_prediction_features(
        df
    )

    # ========================================================
    # 5. GET LATEST SPENDING INFORMATION
    # ========================================================

    latest = df.iloc[-1]

    previous_spending = float(
        latest["daily_spending"]
    )

    last_spending_date = pd.to_datetime(
        latest["date"]
    )

    # ========================================================
    # 6. DETERMINE NEXT CALENDAR DAY
    # ========================================================

    next_date = (
        last_spending_date
        + pd.Timedelta(days=1)
    )

    next_day_of_week = (
        next_date.dayofweek
    )

    # ========================================================
    # 7. CALCULATE RECENT SPENDING AVERAGE
    # ========================================================

    recent_values = (
        df["daily_spending"]
        .tail(3)
    )

    rolling_average = float(
        recent_values.mean()
    )

    # ========================================================
    # 8. NEXT DAY INDEX
    # ========================================================

    next_day_index = len(df)

    # ========================================================
    # 9. CREATE MODEL INPUT
    # ========================================================

    input_data = pd.DataFrame(
        [
            {
                "day_index": next_day_index,
                "day_of_week": next_day_of_week,
                "lag_1": previous_spending,
                "rolling_mean_3": rolling_average
            }
        ]
    )

    # --------------------------------------------------------
    # Make sure columns exactly match training
    # --------------------------------------------------------

    input_data = input_data[
        feature_columns
    ]

    # ========================================================
    # 10. MODEL PREDICTION
    # ========================================================

    prediction = model.predict(
        input_data
    )[0]

    prediction = float(
        prediction
    )

    # --------------------------------------------------------
    # Prevent negative spending prediction
    # --------------------------------------------------------

    prediction = max(
        0.0,
        prediction
    )

    # ========================================================
    # 11. FALLBACK FOR VERY SMALL / IRREGULAR DATASET
    # ========================================================
    #
    # If the model produces zero while recent spending
    # exists, use the recent spending average.
    #
    # This prevents:
    #
    # predicted_spending = ₹0
    #
    # when actual recent purchases exist.
    # ========================================================

    if (
        prediction == 0.0
        and rolling_average > 0
    ):

        prediction = rolling_average

        prediction_source = (
            "recent_spending_fallback"
        )

    else:

        prediction_source = (
            "machine_learning_model"
        )

    # ========================================================
    # 12. RECOMMENDED BUDGET
    # ========================================================
    #
    # Add a 15% safety buffer.
    # ========================================================

    recommended_budget = (
        prediction * 1.15
    )

    # ========================================================
    # 13. RETURN RESULT
    # ========================================================

    return {
        "predicted_spending": round(
            prediction,
            2
        ),

        "recommended_budget": round(
            recommended_budget,
            2
        ),

        "last_daily_spending": round(
            previous_spending,
            2
        ),

        "recent_average_spending": round(
            rolling_average,
            2
        ),

        "last_spending_date": (
            last_spending_date.strftime(
                "%Y-%m-%d"
            )
        ),

        "next_prediction_date": (
            next_date.strftime(
                "%Y-%m-%d"
            )
        ),

        "spending_days": len(df),

        "model_type": model_type,

        "prediction_source": (
            prediction_source
        ),

        "message": (
            "Prediction generated using "
            "SmartPay AI spending model."
        )
    }