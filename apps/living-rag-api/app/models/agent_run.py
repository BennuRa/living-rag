"""SQLAlchemy model for complete Agent executions."""

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
    Integer,
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


class AgentRunStatus(StrEnum):
    """Lifecycle state of a complete Agent run."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AgentRun(Base):
    """A complete execution of an Agent workflow."""

    __tablename__ = "agent_runs"
    __table_args__ = (
        CheckConstraint(
            "duration_ms IS NULL OR duration_ms >= 0",
            name="ck_agent_runs_duration_non_negative",
        ),
        CheckConstraint(
            "input_tokens IS NULL OR input_tokens >= 0",
            name="ck_agent_runs_input_tokens_non_negative",
        ),
        CheckConstraint(
            "output_tokens IS NULL OR output_tokens >= 0",
            name="ck_agent_runs_output_tokens_non_negative",
        ),
        UniqueConstraint(
            "trace_id",
            name="uq_agent_runs_trace_id",
        ),
        Index(
            "ix_agent_runs_thread_id_created_at",
            "thread_id",
            "created_at",
        ),
        Index(
            "ix_agent_runs_status_created_at",
            "status",
            "created_at",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    thread_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey(
            "chat_threads.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )

    message_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey(
            "chat_messages.id",
            ondelete="SET NULL",
        ),
        nullable=True,
    )

    trace_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        nullable=False,
    )

    status: Mapped[AgentRunStatus] = mapped_column(
        Enum(
            AgentRunStatus,
            name="agent_run_status",
            values_callable=lambda enum_class: [
                member.value for member in enum_class
            ],
        ),
        nullable=False,
        default=AgentRunStatus.PENDING,
        server_default=text("'pending'"),
    )

    intent: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
    )

    workflow_version: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default="0.1.0",
        server_default=text("'0.1.0'"),
    )

    model_name: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
    )

    prompt_version: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
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

    input_tokens: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    output_tokens: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    estimated_cost: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 6),
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

    thread: Mapped["ChatThread"] = relationship(
        back_populates="agent_runs",
    )

    message: Mapped["ChatMessage | None"] = relationship(
        back_populates="agent_runs",
    )

    node_runs: Mapped[list["AgentNodeRun"]] = relationship(
        back_populates="agent_run",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="AgentNodeRun.sequence_number",
    )

    tool_calls: Mapped[list["ToolCall"]] = relationship(
        back_populates="agent_run",
        passive_deletes=True,
        order_by="ToolCall.created_at",
    )