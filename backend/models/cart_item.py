from sqlalchemy import (
    Column,
    Integer,
    Numeric,
    ForeignKey
)

from database import Base


class CartItem(Base):
    __tablename__ = "cart_items"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    cart_id = Column(
        Integer,
        ForeignKey("carts.id"),
        nullable=False
    )

    product_id = Column(
        Integer,
        ForeignKey("products.id"),
        nullable=False
    )

    quantity = Column(
        Integer,
        default=1,
        nullable=False
    )

    unit_price = Column(
        Numeric(12, 2),
        nullable=False
    )

    subtotal = Column(
        Numeric(12, 2),
        nullable=False
    )