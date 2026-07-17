"""SQLAlchemy model for auditable business events."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import (
    DateTime,
    Enum,
    Index,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class AuditActorType(StrEnum):
    """Type of actor that caused an auditable event."""

    USER = "user"
    AGENT = "agent"
    SYSTEM = "system"
    ADMIN = "admin"


class AuditResult(StrEnum):
    """Result of an auditable action."""

    SUCCESS = "success"
    FAILURE = "failure"
    DENIED = "denied"
    PENDING = "pending"


class AuditLog(Base):
    """An immutable-intent record of a security or business event."""

    __tablename__ = "audit_logs"
    __table_args__ = (
        Index(
            "ix_audit_logs_resource_type_resource_id",
            "resource_type",
            "resource_id",
        ),
        Index(
            "ix_audit_logs_trace_id_created_at",
            "trace_id",
            "created_at",
        ),
        Index(
            "ix_audit_logs_actor_type_actor_id",
            "actor_type",
            "actor_id",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    actor_type: Mapped[AuditActorType] = mapped_column(
        Enum(
            AuditActorType,
            name="audit_actor_type",
            values_callable=lambda enum_class: [
                member.value for member in enum_class
            ],
        ),
        nullable=False,
    )

    actor_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        nullable=True,
    )

    action: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
    )

    resource_type: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
    )

    resource_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        nullable=True,
    )

    result: Mapped[AuditResult] = mapped_column(
        Enum(
            AuditResult,
            name="audit_result",
            values_callable=lambda enum_class: [
                member.value for member in enum_class
            ],
        ),
        nullable=False,
    )

    reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    before_snapshot: Mapped[dict[str, object]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )

    after_snapshot: Mapped[dict[str, object]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )

    trace_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
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