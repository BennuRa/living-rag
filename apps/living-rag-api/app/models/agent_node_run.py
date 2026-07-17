"""SQLAlchemy model for Agent graph node executions."""

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
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class AgentNodeRunStatus(StrEnum):
    """Lifecycle state of one Agent node execution."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SKIPPED = "skipped"


class AgentNodeRun(Base):
    """Execution record for one node inside an Agent run."""

    __tablename__ = "agent_node_runs"
    __table_args__ = (
        CheckConstraint(
            "sequence_number > 0",
            name="ck_agent_node_runs_sequence_number_positive",
        ),
        CheckConstraint(
            "duration_ms IS NULL OR duration_ms >= 0",
            name="ck_agent_node_runs_duration_non_negative",
        ),
        UniqueConstraint(
            "agent_run_id",
            "sequence_number",
            name="uq_agent_node_runs_run_id_sequence_number",
        ),
        Index(
            "ix_agent_node_runs_agent_run_id_status",
            "agent_run_id",
            "status",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    agent_run_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey(
            "agent_runs.id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )

    node_name: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
    )

    sequence_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    status: Mapped[AgentNodeRunStatus] = mapped_column(
        Enum(
            AgentNodeRunStatus,
            name="agent_node_run_status",
            values_callable=lambda enum_class: [
                member.value for member in enum_class
            ],
        ),
        nullable=False,
        default=AgentNodeRunStatus.PENDING,
        server_default=text("'pending'"),
    )

    input_snapshot: Mapped[dict[str, object]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )

    output_snapshot: Mapped[dict[str, object]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )

    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    duration_ms: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    error_code: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
    )

    error_message: Mapped[str | None] = mapped_column(
        Text,
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

    agent_run: Mapped["AgentRun"] = relationship(
        back_populates="node_runs",
    )

    tool_calls: Mapped[list["ToolCall"]] = relationship(
        back_populates="node_run",
        passive_deletes=True,
        order_by="ToolCall.created_at",
    )