from decimal import Decimal, InvalidOperation

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from database import get_db
from models.product import Product
from models.user import User
from routers.users import get_current_user


router = APIRouter(
    prefix="/product-registration",
    tags=["Product Registration"]
)


class RegisterProductRequest(BaseModel):
    barcode: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1)
    brand: str | None = None
    category: str | None = None
    price: Decimal = Field(..., gt=0)


@router.post("/")
def register_product(
    product_data: RegisterProductRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Register an externally identified product into
    the SmartPay product database with a trusted price.

    This endpoint does NOT add the product to a cart
    and does NOT deduct wallet money.
    """

    barcode = product_data.barcode.strip()
    name = product_data.name.strip()

    if not barcode:
        raise HTTPException(
            status_code=400,
            detail="Barcode cannot be empty"
        )

    if not name:
        raise HTTPException(
            status_code=400,
            detail="Product name cannot be empty"
        )

    # ---------------------------------------------------------
    # Check whether barcode already exists
    # ---------------------------------------------------------

    existing_product = (
        db.query(Product)
        .filter(Product.barcode == barcode)
        .first()
    )

    if existing_product:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "Product with this barcode already exists",
                "product_id": existing_product.id,
                "barcode": existing_product.barcode
            }
        )

    # ---------------------------------------------------------
    # Validate price
    # ---------------------------------------------------------

    try:
        price = Decimal(str(product_data.price))
    except (InvalidOperation, ValueError):
        raise HTTPException(
            status_code=400,
            detail="Invalid product price"
        )

    if price <= Decimal("0.00"):
        raise HTTPException(
            status_code=400,
            detail="Product price must be greater than zero"
        )

    # ---------------------------------------------------------
    # Create SmartPay product
    # ---------------------------------------------------------

    product = Product(
        barcode=barcode,
        name=name,
        brand=(
            product_data.brand.strip()
            if product_data.brand
            else None
        ),
        category=(
            product_data.category.strip()
            if product_data.category
            else None
        ),
        price=price
    )

    db.add(product)

    try:
        db.commit()
        db.refresh(product)

    except Exception:
        db.rollback()

        raise HTTPException(
            status_code=500,
            detail="Unable to save product"
        )

    # ---------------------------------------------------------
    # Return registered product
    # ---------------------------------------------------------

    return {
        "message": "Product registered successfully",
        "source": "smartpay_database",
        "product": {
            "id": product.id,
            "barcode": product.barcode,
            "name": product.name,
            "brand": product.brand,
            "category": product.category,
            "price": float(product.price)
        }
    }