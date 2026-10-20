from datetime import datetime
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from app.models.refund import Refund

from sqlalchemy import DateTime, ForeignKey, Boolean, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.database import Base

class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )

    amount: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    currency: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
        default="INR",
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pending",
        index=True,
    )

    stripe_payment_intent_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        unique=True,
        index=True,
    )

    idempotency_key: Mapped[str] = mapped_column(
    String(255),
    nullable=False,
    unique=True,
    index=True,
    )

    webhook_event_id: Mapped[str | None] = mapped_column(
    String(255),
    nullable=True,
    unique=True,
    index=True,
    )
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    is_suspicious: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    fraud_score: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    fraud_reasons: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    refunded_amount: Mapped[int] = mapped_column(
    Integer,
    nullable=False,
    default=0,
    )

    refunds: Mapped[list["Refund"]] = relationship(
    back_populates="payment",
    cascade="all, delete-orphan",
    )