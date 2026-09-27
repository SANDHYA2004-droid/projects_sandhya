from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import requests

from database import get_db
from models.user import User
from models.product import Product
from routers.users import get_current_user


router = APIRouter(
    prefix="/scanner",
    tags=["Barcode Scanner"]
)


OPEN_FOOD_FACTS_URL = (
    "https://world.openfoodfacts.org/api/v2/product/{barcode}.json"
)


@router.get("/{barcode}")
def scan_product(
    barcode: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Scan a product barcode.

    Lookup order:
    1. SmartPay PostgreSQL database
    2. Open Food Facts API

    This endpoint ONLY identifies the product.
    It does NOT add the product to the cart
    and does NOT deduct money.
    """

    barcode = barcode.strip()

    if not barcode:
        raise HTTPException(
            status_code=400,
            detail="Barcode cannot be empty"
        )

    # ---------------------------------------------------------
    # STEP 1: Search SmartPay's own product database
    # ---------------------------------------------------------

    product = (
        db.query(Product)
        .filter(Product.barcode == barcode)
        .first()
    )

    if product:
        return {
            "message": "Product found in SmartPay database",
            "source": "smartpay_database",
            "product": {
                "id": product.id,
                "name": product.name,
                "brand": product.brand,
                "category": product.category,
                "barcode": product.barcode,
                "price": float(product.price)
            }
        }

    # ---------------------------------------------------------
    # STEP 2: Product not in SmartPay DB
    #         Search Open Food Facts
    # ---------------------------------------------------------

    try:
        response = requests.get(
            OPEN_FOOD_FACTS_URL.format(barcode=barcode),
            timeout=10,
            headers={
                "User-Agent": "SmartPayAI/1.0"
            }
        )

    except requests.RequestException as exc:
        print(
            "Open Food Facts API error:",
            exc
        )

        raise HTTPException(
            status_code=503,
            detail=(
                "Product database temporarily unavailable. "
                "Please try again."
            )
        )

    if response.status_code != 200:
        raise HTTPException(
            status_code=404,
            detail=f"Product with barcode {barcode} not found"
        )

    try:
        data = response.json()
    except ValueError:
        raise HTTPException(
            status_code=502,
            detail="Invalid response from product database"
        )

    # Open Food Facts uses status = 1 when product exists
    if data.get("status") != 1:
        raise HTTPException(
            status_code=404,
            detail=f"Product with barcode {barcode} not found"
        )

    product_data = data.get("product") or {}

    # ---------------------------------------------------------
    # Extract product information
    # ---------------------------------------------------------

    product_name = (
        product_data.get("product_name")
        or product_data.get("product_name_en")
        or ""
    ).strip()

    brand = (
        product_data.get("brands")
        or ""
    ).strip()

    category = (
        product_data.get("categories")
        or ""
    ).strip()

    image_url = (
        product_data.get("image_front_url")
        or product_data.get("image_url")
        or None
    )

    # ---------------------------------------------------------
    # Product must have at least a usable name
    # ---------------------------------------------------------

    if not product_name:
        raise HTTPException(
            status_code=404,
            detail=(
                f"Barcode {barcode} was found, "
                "but usable product information was not available."
            )
        )

    # ---------------------------------------------------------
    # IMPORTANT:
    #
    # Open Food Facts is being used here for PRODUCT
    # IDENTIFICATION.
    #
    # We do NOT use an external price blindly for payment.
    # ---------------------------------------------------------

    return {
        "message": "Product found through external product database",
        "source": "open_food_facts",
        "product": {
            "id": None,
            "name": product_name,
            "brand": brand or None,
            "category": category or None,
            "barcode": barcode,
            "price": None,
            "image_url": image_url,
            "price_status": "PRICE_REQUIRES_VERIFICATION"
        }
    }