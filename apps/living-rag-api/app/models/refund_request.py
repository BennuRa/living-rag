"""SQLAlchemy model for order refund requests."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class RefundRequestStatus(StrEnum):
    """Lifecycle state of a refund request."""

    PENDING = "pending"
    REVIEWING = "reviewing"
    APPROVED = "approved"
    REJECTED = "rejected"
    PROCESSING = "processing"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class RefundRequest(Base):
    """A traceable refund request submitted for one order."""

    __tablename__ = "refund_requests"
    __table_args__ = (
        CheckConstraint(
            "requested_amount > 0",
            name="ck_refund_requests_requested_amount_positive",
        ),
        CheckConstraint(
            "approved_amount IS NULL OR approved_amount > 0",
            name="ck_refund_requests_approved_amount_positive",
        ),
        CheckConstraint(
            "approved_amount IS NULL OR approved_amount <= requested_amount",
            name="ck_refund_requests_approved_amount_lte_requested",
        ),
        UniqueConstraint(
            "request_number",
            name="uq_refund_requests_request_number",
        ),
        Index(
            "ix_refund_requests_order_id_status",
            "order_id",
            "status",
        ),
        Index(
            "ix_refund_requests_requested_at",
            "requested_at",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    order_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey(
            "orders.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )

    request_number: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )

    status: Mapped[RefundRequestStatus] = mapped_column(
        Enum(
            RefundRequestStatus,
            name="refund_request_status",
            values_callable=lambda enum_class: [
                member.value for member in enum_class
            ],
        ),
        nullable=False,
        default=RefundRequestStatus.PENDING,
        server_default=text("'pending'"),
    )

    requested_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
    )

    approved_amount: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2),
        nullable=True,
    )

    reason: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    rejection_reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    metadata_: Mapped[dict[str, object]] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    order: Mapped["Order"] = relationship(
        back_populates="refund_requests",
    )