"""SQLAlchemy model for conversation messages."""

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
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class ChatMessageRole(StrEnum):
    """Role that produced a chat message."""

    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL = "tool"


class ChatMessageStatus(StrEnum):
    """Processing state of a chat message."""

    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"


class ChatMessage(Base):
    """One ordered message inside a conversation thread."""

    __tablename__ = "chat_messages"
    __table_args__ = (
        CheckConstraint(
            "sequence_number > 0",
            name="ck_chat_messages_sequence_number_positive",
        ),
        CheckConstraint(
            "length(regexp_replace(content, '[[:space:]]', '', 'g')) > 0",
            name="ck_chat_messages_content_not_blank",
        ),
        UniqueConstraint(
            "thread_id",
            "sequence_number",
            name="uq_chat_messages_thread_id_sequence_number",
        ),
        Index(
            "ix_chat_messages_thread_id_created_at",
            "thread_id",
            "created_at",
        ),
        Index(
            "ix_chat_messages_trace_id",
            "trace_id",
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
            ondelete="CASCADE",
        ),
        nullable=False,
    )

    sequence_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    role: Mapped[ChatMessageRole] = mapped_column(
        Enum(
            ChatMessageRole,
            name="chat_message_role",
            values_callable=lambda enum_class: [
                member.value for member in enum_class
            ],
        ),
        nullable=False,
    )

    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    status: Mapped[ChatMessageStatus] = mapped_column(
        Enum(
            ChatMessageStatus,
            name="chat_message_status",
            values_callable=lambda enum_class: [
                member.value for member in enum_class
            ],
        ),
        nullable=False,
        default=ChatMessageStatus.PENDING,
        server_default=text("'pending'"),
    )

    trace_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        nullable=True,
    )

    citations: Mapped[list[dict[str, object]]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default=text("'[]'::jsonb"),
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
        back_populates="messages",
    )

    agent_runs: Mapped[list["AgentRun"]] = relationship(
        back_populates="message",
        passive_deletes=True,
        order_by="AgentRun.created_at",
    )