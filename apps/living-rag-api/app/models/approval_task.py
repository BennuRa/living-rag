"""SQLAlchemy model for business approval tasks."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4
from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Index,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ApprovalTaskType(StrEnum):
    """Business operation types that require approval."""

    REFUND_REQUEST = "refund_request"
    DIRECT_REFUND = "direct_refund"
    MODIFY_POLICY = "modify_policy"
    DELETE_DOCUMENT = "delete_document"


class ApprovalTaskStatus(StrEnum):
    """Lifecycle state of an approval task."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


class ApprovalDecision(StrEnum):
    """Human decision made on an approval task."""

    APPROVE = "approve"
    REJECT = "reject"


class ApprovalTask(Base):
    """A human approval task for a side-effecting business operation."""

    __tablename__ = "approval_tasks"
    __table_args__ = (
        Index(
            "ix_approval_tasks_status",
            "status",
        ),
        Index(
            "ix_approval_tasks_task_type",
            "task_type",
        ),
        Index(
            "ix_approval_tasks_resource_type_resource_id",
            "resource_type",
            "resource_id",
        ),
        Index(
            "ix_approval_tasks_trace_id",
            "trace_id",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    task_type: Mapped[ApprovalTaskType] = mapped_column(
        Enum(
            ApprovalTaskType,
            name="approval_task_type",
            values_callable=lambda enum_class: [
                member.value for member in enum_class
            ],
        ),
        nullable=False,
    )

    status: Mapped[ApprovalTaskStatus] = mapped_column(
        Enum(
            ApprovalTaskStatus,
            name="approval_task_status",
            values_callable=lambda enum_class: [
                member.value for member in enum_class
            ],
        ),
        nullable=False,
        default=ApprovalTaskStatus.PENDING,
        server_default=text("'pending'"),
    )

    refund_request_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey(
            "refund_requests.id",
            ondelete="RESTRICT",
        ),
        nullable=True,
    )

    resource_type: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )

    resource_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        nullable=True,
    )

    requested_by: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey(
            "users.id",
            ondelete="SET NULL",
        ),
        nullable=True,
    )

    trace_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        nullable=True,
    )

    reason: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    decision: Mapped[ApprovalDecision | None] = mapped_column(
        Enum(
            ApprovalDecision,
            name="approval_decision",
            values_callable=lambda enum_class: [
                member.value for member in enum_class
            ],
        ),
        nullable=True,
    )

    decision_reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    decided_by: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey(
            "users.id",
            ondelete="SET NULL",
        ),
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

    decided_at: Mapped[datetime | None] = mapped_column(
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