"""SQLAlchemy model for Agent tool calls."""

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
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class ToolCallStatus(StrEnum):
    """Execution state of a tool call."""

    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    TIMEOUT = "timeout"


class ToolCall(Base):
    """One interaction between an Agent and a business or retrieval tool."""

    __tablename__ = "tool_calls"
    __table_args__ = (
        CheckConstraint(
            "duration_ms IS NULL OR duration_ms >= 0",
            name="ck_tool_calls_duration_non_negative",
        ),
        Index(
            "ix_tool_calls_agent_run_id_status",
            "agent_run_id",
            "status",
        ),
        Index(
            "ix_tool_calls_tool_name_created_at",
            "tool_name",
            "created_at",
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

    node_run_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey(
            "agent_node_runs.id",
            ondelete="SET NULL",
        ),
        nullable=True,
    )

    tool_name: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
    )

    status: Mapped[ToolCallStatus] = mapped_column(
        Enum(
            ToolCallStatus,
            name="tool_call_status",
            values_callable=lambda enum_class: [
                member.value for member in enum_class
            ],
        ),
        nullable=False,
        default=ToolCallStatus.PENDING,
        server_default=text("'pending'"),
    )

    arguments: Mapped[dict[str, object]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )

    result: Mapped[dict[str, object]] = mapped_column(
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
        back_populates="tool_calls",
    )

    node_run: Mapped["AgentNodeRun | None"] = relationship(
        back_populates="tool_calls",
    )