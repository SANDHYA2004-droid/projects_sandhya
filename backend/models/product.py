from datetime import datetime

from sqlalchemy import (
    Column,
    Integer,
    String,
    Numeric,
    DateTime
)

from database import Base


class Product(Base):
    __tablename__ = "products"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    barcode = Column(
        String(100),
        unique=True,
        index=True,
        nullable=False
    )

    name = Column(
        String(255),
        nullable=False
    )

    category = Column(
        String(100),
        nullable=False
    )

    price = Column(
        Numeric(12, 2),
        nullable=False
    )

    brand = Column(
        String(100),
        nullable=True
    )

    sustainability_score = Column(
        Numeric(5, 2),
        nullable=True
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow
    )