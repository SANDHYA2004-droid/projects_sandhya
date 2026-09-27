from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from models.product import Product
from routers.users import get_current_user


router = APIRouter(
    prefix="/products",
    tags=["Products"]
)


@router.post("/create")
def create_product(
    barcode: str,
    name: str,
    category: str,
    price: Decimal,
    brand: str = None,
    sustainability_score: Decimal = None,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    existing_product = (
        db.query(Product)
        .filter(Product.barcode == barcode)
        .first()
    )

    if existing_product:
        raise HTTPException(
            status_code=400,
            detail="Product with this barcode already exists"
        )

    if price <= 0:
        raise HTTPException(
            status_code=400,
            detail="Price must be greater than zero"
        )

    product = Product(
        barcode=barcode,
        name=name,
        category=category,
        price=price,
        brand=brand,
        sustainability_score=sustainability_score
    )

    db.add(product)
    db.commit()
    db.refresh(product)

    return {
        "message": "Product created successfully",
        "product": {
            "id": product.id,
            "barcode": product.barcode,
            "name": product.name,
            "category": product.category,
            "price": product.price,
            "brand": product.brand,
            "sustainability_score": product.sustainability_score
        }
    }


@router.get("/{barcode}")
def get_product_by_barcode(
    barcode: str,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    product = (
        db.query(Product)
        .filter(Product.barcode == barcode)
        .first()
    )

    if not product:
        raise HTTPException(
            status_code=404,
            detail="Product not found"
        )

    return {
        "id": product.id,
        "barcode": product.barcode,
        "name": product.name,
        "category": product.category,
        "price": product.price,
        "brand": product.brand,
        "sustainability_score": product.sustainability_score
    }


@router.get("/")
def get_products(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    products = (
        db.query(Product)
        .order_by(Product.name)
        .all()
    )

    return [
        {
            "id": product.id,
            "barcode": product.barcode,
            "name": product.name,
            "category": product.category,
            "price": product.price,
            "brand": product.brand,
            "sustainability_score": product.sustainability_score
        }
        for product in products
    ]