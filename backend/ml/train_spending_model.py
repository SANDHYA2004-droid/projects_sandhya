from pathlib import Path

import joblib
import pandas as pd

from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LinearRegression

from database import SessionLocal
from models.transaction import Transaction


# ============================================================
# PATHS
# ============================================================

MODEL_DIR = Path(__file__).resolve().parent

MODEL_PATH = MODEL_DIR / "spending_model.pkl"


# ============================================================
# LOAD SPENDING DATA
# ============================================================

def load_spending_data(db):

    transactions = (
        db.query(Transaction)
        .filter(
            Transaction.transaction_type == "PURCHASE",
            Transaction.status == "SUCCESS"
        )
        .order_by(
            Transaction.created_at.asc()
        )
        .all()
    )

    if not transactions:
        return pd.DataFrame()

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
    # Combine all purchases made on the same day
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

def create_features(df):

    df = df.copy()

    # Convert date to pandas datetime
    df["date"] = pd.to_datetime(
        df["date"]
    )

    # --------------------------------------------------------
    # Sequential day index
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
    # Previous 3-day average
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
# TRAIN MODEL
# ============================================================

def train_model():

    db = SessionLocal()

    try:

        print()
        print("======================================")
        print("   SmartPay AI Spending ML Training")
        print("======================================")
        print()

        # ====================================================
        # 1. LOAD DATA
        # ====================================================

        df = load_spending_data(db)

        if df.empty:

            print("No successful purchase data found.")
            print()
            print(
                "Please create some successful purchase "
                "transactions before training the model."
            )

            return

        print(
            f"Total spending days found: {len(df)}"
        )

        print()
        print("Daily spending:")
        print(
            df.to_string(
                index=False
            )
        )

        # ====================================================
        # 2. CREATE FEATURES
        # ====================================================

        feature_df = create_features(df)

        # ----------------------------------------------------
        # Remove rows where lagged features are unavailable
        # ----------------------------------------------------

        training_df = feature_df.dropna(
            subset=[
                "lag_1",
                "rolling_mean_3"
            ]
        ).copy()

        print()
        print(
            f"Training samples: {len(training_df)}"
        )

        # ====================================================
        # 3. CHECK MINIMUM DATA
        # ====================================================

        if len(training_df) < 2:

            print()
            print(
                "Not enough training samples."
            )

            print(
                "At least 2 usable training samples "
                "are required."
            )

            print()
            print(
                "Please add more successful purchase "
                "transactions and train again."
            )

            return

        # ====================================================
        # 4. PREPARE FEATURES
        # ====================================================

        feature_columns = [
            "day_index",
            "day_of_week",
            "lag_1",
            "rolling_mean_3"
        ]

        X = training_df[
            feature_columns
        ]

        y = training_df[
            "daily_spending"
        ]

        # ====================================================
        # 5. SELECT MODEL
        # ====================================================

        if len(training_df) < 10:

            print()
            print(
                "Using Linear Regression because "
                "the current dataset is small..."
            )

            model = LinearRegression()

            model_type = "LinearRegression"

        else:

            print()
            print(
                "Using Random Forest because "
                "enough training data is available..."
            )

            model = RandomForestRegressor(
                n_estimators=100,
                random_state=42
            )

            model_type = "RandomForestRegressor"

        # ====================================================
        # 6. TRAIN
        # ====================================================

        model.fit(
            X,
            y
        )

        # ====================================================
        # 7. SAVE MODEL
        # ====================================================

        model_package = {
    "model": model,
    "feature_columns": feature_columns,
    "model_type": model_type
}

        joblib.dump(
            model_package,
            MODEL_PATH
        )

        # ====================================================
        # 8. SUCCESS MESSAGE
        # ====================================================

        print()
        print("======================================")
        print("✅ MODEL TRAINED SUCCESSFULLY")
        print("======================================")

        print()
        print(
            f"Model type: {model_type}"
        )

        print(
            f"Spending days: {len(df)}"
        )

        print(
            f"Training samples: {len(training_df)}"
        )

        print(
            f"Last spending date: "
            f"{df['date'].max()}"
        )

        print(
            f"Last daily spending: "
            f"₹{df['daily_spending'].iloc[-1]:.2f}"
        )

        print()
        print("Model saved at:")

        print(
            MODEL_PATH
        )

        # ====================================================
        # 9. DEVELOPMENT WARNING
        # ====================================================

        if len(df) < 10:

            print()
            print("⚠️ Important:")

            print(
                "The current dataset is very small. "
                "This model is a development prototype."
            )

            print(
                "Prediction quality will improve as more "
                "real purchase history is collected."
            )

        else:

            print()
            print(
                "The model has enough data for a "
                "better development-stage prediction."
            )

    finally:

        db.close()


# ============================================================
# RUN TRAINING
# ============================================================

if __name__ == "__main__":

    train_model()