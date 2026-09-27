from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from models.user import User
from models.cart import Cart
from models.cart_item import CartItem
from models.product import Product
from routers.users import get_current_user


router = APIRouter(
    prefix="/cart",
    tags=["Smart Cart"]
)


def get_active_cart(
    user_id: int,
    db: Session
):
    cart = (
        db.query(Cart)
        .filter(
            Cart.user_id == user_id,
            Cart.status == "ACTIVE"
        )
        .first()
    )

    if not cart:
        cart = Cart(
            user_id=user_id,
            status="ACTIVE",
            total_amount=Decimal("0.00")
        )

        db.add(cart)
        db.commit()
        db.refresh(cart)

    return cart


@router.get("/")
def get_cart(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    cart = get_active_cart(
        current_user.id,
        db
    )

    items = (
        db.query(CartItem, Product)
        .join(
            Product,
            CartItem.product_id == Product.id
        )
        .filter(CartItem.cart_id == cart.id)
        .all()
    )

    return {
        "cart_id": cart.id,
        "status": cart.status,
        "total_amount": cart.total_amount,
        "items": [
            {
                "cart_item_id": item.id,
                "product_id": product.id,
                "barcode": product.barcode,
                "name": product.name,
                "category": product.category,
                "brand": product.brand,
                "quantity": item.quantity,
                "unit_price": item.unit_price,
                "subtotal": item.subtotal
            }
            for item, product in items
        ]
    }


@router.post("/add")
def add_to_cart(
    barcode: str,
    quantity: int = 1,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if quantity <= 0:
        raise HTTPException(
            status_code=400,
            detail="Quantity must be greater than zero"
        )

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

    cart = get_active_cart(
        current_user.id,
        db
    )

    existing_item = (
        db.query(CartItem)
        .filter(
            CartItem.cart_id == cart.id,
            CartItem.product_id == product.id
        )
        .first()
    )

    if existing_item:
        existing_item.quantity += quantity

        existing_item.subtotal = (
            existing_item.unit_price *
            existing_item.quantity
        )

    else:
        subtotal = (
            product.price *
            quantity
        )

        cart_item = CartItem(
            cart_id=cart.id,
            product_id=product.id,
            quantity=quantity,
            unit_price=product.price,
            subtotal=subtotal
        )

        db.add(cart_item)

    db.flush()

    items = (
        db.query(CartItem)
        .filter(CartItem.cart_id == cart.id)
        .all()
    )

    cart.total_amount = sum(
        (item.subtotal for item in items),
        Decimal("0.00")
    )

    db.commit()
    db.refresh(cart)

    return {
        "message": "Product added to cart",
        "cart_id": cart.id,
        "product": product.name,
        "quantity_added": quantity,
        "total_amount": cart.total_amount
    }


@router.delete("/remove/{cart_item_id}")
def remove_from_cart(
    cart_item_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    cart = (
        db.query(Cart)
        .filter(
            Cart.user_id == current_user.id,
            Cart.status == "ACTIVE"
        )
        .first()
    )

    if not cart:
        raise HTTPException(
            status_code=404,
            detail="Active cart not found"
        )

    item = (
        db.query(CartItem)
        .filter(
            CartItem.id == cart_item_id,
            CartItem.cart_id == cart.id
        )
        .first()
    )

    if not item:
        raise HTTPException(
            status_code=404,
            detail="Cart item not found"
        )

    db.delete(item)
    db.flush()

    items = (
        db.query(CartItem)
        .filter(CartItem.cart_id == cart.id)
        .all()
    )

    cart.total_amount = sum(
        (item.subtotal for item in items),
        Decimal("0.00")
    )

    db.commit()

    return {
        "message": "Product removed from cart",
        "cart_id": cart.id,
        "total_amount": cart.total_amount
    }