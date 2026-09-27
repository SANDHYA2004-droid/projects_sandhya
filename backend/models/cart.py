from datetime import datetime

from sqlalchemy import (
    Column,
    Integer,
    Numeric,
    String,
    DateTime,
    ForeignKey
)

from database import Base


class Cart(Base):
    __tablename__ = "carts"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    user_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=False
    )

    status = Column(
        String(20),
        default="ACTIVE",
        nullable=False
    )

    total_amount = Column(
        Numeric(12, 2),
        default=0.00,
        nullable=False
    )

    shopping_intent = Column(
        String(100),
        nullable=True
    )

    intent_source = Column(
        String(30),
        nullable=True
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow
    )