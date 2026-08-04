from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING
from uuid import UUID, uuid4
from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base

if TYPE_CHECKING:
    from app.models.policy_conflict import PolicyConflict


class ReviewTaskType(StrEnum):
    RESOLVE_CONFLICT = "resolve_conflict"
    INVALIDATE_DOCUMENT = "invalidate_document" 


class ReviewTaskStatus(StrEnum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class ReviewDecision(StrEnum):
    APPROVE = "approve"
    REJECT = "reject"
    INVALIDATE_DOCUMENT = "invalidate_document"


class ReviewTask(Base):
    """One human review task created from a policy conflict."""

    __tablename__ = "review_tasks"
    __table_args__ = (
        Index(
            "ix_review_tasks_status",
            "status",
        ),
        Index(
            "ix_review_tasks_conflict_id",
            "conflict_id",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    conflict_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey(
            "conflicts.id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )

    task_type: Mapped[ReviewTaskType] = mapped_column(
        String(64),
        nullable=False,
        default=ReviewTaskType.RESOLVE_CONFLICT,
        server_default=text("'resolve_conflict'"),
    )

    status: Mapped[ReviewTaskStatus] = mapped_column(
        String(32),
        nullable=False,
        default=ReviewTaskStatus.PENDING,
        server_default=text("'pending'"),
    )

    assigned_to: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        nullable=True,
    )
    decision: Mapped[ReviewDecision | None] = mapped_column(
        String(32),
        nullable=True,
    )
    decision_reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
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

    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    conflict: Mapped["PolicyConflict"] = relationship()