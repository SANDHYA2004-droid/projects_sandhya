from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from database import engine, Base

# Models
from models.user import User
from models.wallet import Wallet
from models.transaction import Transaction
from models.product import Product
from models.cart import Cart
from models.cart_item import CartItem
from models.budget import Budget

# Routers
from routers.auth import router as auth_router
from routers.users import router as users_router
from routers.wallet import router as wallet_router
from routers.product import router as product_router
from routers.cart import router as cart_router
from routers.budget import router as budget_router
from routers.optimization import router as optimization_router
from routers.analytics import router as analytics_router
from routers.personalized_budget import router as personalized_budget_router
from routers.checkout import router as checkout_router
from routers.receipt import router as receipt_router
from routers.shopping_intent import router as shopping_intent_router
from routers.ai import router as ai_router
from routers.scanner import router as scanner_router
from routers.product_registration import (
    router as product_registration_router
)
from routers.budget import router as budget_router




# ============================================================
# FASTAPI APPLICATION
# ============================================================

app = FastAPI(
    title="SmartPay AI API",
    description="Backend API for SmartPay AI",
    version="1.0.0"
)


# ============================================================
# DATABASE INITIALIZATION
# ============================================================

Base.metadata.create_all(bind=engine)


# ============================================================
# CORS CONFIGURATION
# ============================================================
# Allows the Next.js frontend running on port 3000
# to communicate with the FastAPI backend running on port 8000.

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://192.168.0.108:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# ROUTERS
# ============================================================

app.include_router(auth_router)
app.include_router(users_router)
app.include_router(wallet_router)
app.include_router(product_router)
app.include_router(cart_router)
app.include_router(budget_router)
app.include_router(optimization_router)
app.include_router(analytics_router)
app.include_router(personalized_budget_router)
app.include_router(checkout_router)
app.include_router(receipt_router)
app.include_router(shopping_intent_router)
app.include_router(ai_router)
app.include_router(scanner_router)
app.include_router(scanner_router)
app.include_router(product_registration_router)
app.include_router(budget_router)

# ============================================================
# ROOT ENDPOINT
# ============================================================

@app.get("/")
def root():
    return {
        "message": "SmartPay AI Backend is running!"
    }


# ============================================================
# HEALTH CHECK
# ============================================================

@app.get("/health")
def health_check():
    return {
        "status": "healthy"
    }


# ============================================================
# DATABASE STATUS
# ============================================================

@app.get("/database-status")
def database_status():
    try:
        with engine.connect() as connection:
            return {
                "database": "connected",
                "status": "healthy"
            }

    except Exception as e:
        return {
            "database": "connection failed",
            "status": "unhealthy",
            "error": str(e)
        }