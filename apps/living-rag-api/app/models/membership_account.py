"""SQLAlchemy model for membership accounts."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class MembershipTier(StrEnum):
    """Membership level of an account."""

    STANDARD = "standard"
    SILVER = "silver"
    GOLD = "gold"
    PLATINUM = "platinum"


class MembershipAccountStatus(StrEnum):
    """Lifecycle state of a membership account."""

    ACTIVE = "active"
    SUSPENDED = "suspended"
    EXPIRED = "expired"
    CLOSED = "closed"


class MembershipAccount(Base):
    """A membership account owned by one application user."""

    __tablename__ = "membership_accounts"
    __table_args__ = (
        CheckConstraint(
            "points >= 0",
            name="ck_membership_accounts_points_non_negative",
        ),
        UniqueConstraint(
            "user_id",
            name="uq_membership_accounts_user_id",
        ),
        UniqueConstraint(
            "membership_number",
            name="uq_membership_accounts_membership_number",
        ),
        Index(
            "ix_membership_accounts_status_created_at",
            "status",
            "created_at",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    user_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey(
            "users.id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )

    membership_number: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )

    tier: Mapped[MembershipTier] = mapped_column(
        Enum(
            MembershipTier,
            name="membership_tier",
            values_callable=lambda enum_class: [
                member.value for member in enum_class
            ],
        ),
        nullable=False,
        default=MembershipTier.STANDARD,
        server_default=text("'standard'"),
    )

    status: Mapped[MembershipAccountStatus] = mapped_column(
        Enum(
            MembershipAccountStatus,
            name="membership_account_status",
            values_callable=lambda enum_class: [
                member.value for member in enum_class
            ],
        ),
        nullable=False,
        default=MembershipAccountStatus.ACTIVE,
        server_default=text("'active'"),
    )

    points: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0"),
    )

    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    expires_at: Mapped[datetime | None] = mapped_column(
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

    user: Mapped["User"] = relationship(
        back_populates="membership_account",
    )

    orders: Mapped[list["Order"]] = relationship(
        back_populates="membership_account",
        order_by="Order.ordered_at",
        passive_deletes=True,
    )