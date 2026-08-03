"""SQLAlchemy models for policy conflicts and their evidences."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
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


class PolicyConflictStatus(StrEnum):
    """Lifecycle state of one policy conflict."""

    OPEN = "open"
    RESOLVED = "resolved"
    DISMISSED = "dismissed"


class PolicyConflict(Base):
    """A persisted comparison result between two policy rules."""

    __tablename__ = "conflicts"
    __table_args__ = (
        Index(
            "ix_conflicts_rule_key",
            "rule_key",
        ),
        Index(
            "ix_conflicts_status",
            "status",
        ),
        Index(
            "ix_conflicts_left_document_version_id",
            "left_document_version_id",
        ),
        Index(
            "ix_conflicts_right_document_version_id",
            "right_document_version_id",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    kind: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )

    severity: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )

    rule_key: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
    )

    left_rule_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey(
            "policy_rules.id",
            ondelete="SET NULL",
        ),
        nullable=True,
    )

    right_rule_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey(
            "policy_rules.id",
            ondelete="SET NULL",
        ),
        nullable=True,
    )

    left_document_version_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey(
            "document_versions.id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )

    right_document_version_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey(
            "document_versions.id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )

    reason: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    recommended_action: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    status: Mapped[PolicyConflictStatus] = mapped_column(
        String(32),
        nullable=False,
        default=PolicyConflictStatus.OPEN,
        server_default=text("'open'"),
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

    evidences: Mapped[list["ConflictEvidence"]] = relationship(
        back_populates="conflict",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="ConflictEvidence.position",
    )


class ConflictEvidence(Base):
    """Original evidence associated with one persisted conflict."""

    __tablename__ = "conflict_evidences"
    __table_args__ = (
        Index(
            "ix_conflict_evidences_conflict_id",
            "conflict_id",
        ),
        Index(
            "ix_conflict_evidences_document_version_id",
            "document_version_id",
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

    rule_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey(
            "policy_rules.id",
            ondelete="SET NULL",
        ),
        nullable=True,
    )

    document_version_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey(
            "document_versions.id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )

    quote: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    position: Mapped[int] = mapped_column(
        nullable=False,
    )

    conflict: Mapped["PolicyConflict"] = relationship(
        back_populates="evidences",
    )