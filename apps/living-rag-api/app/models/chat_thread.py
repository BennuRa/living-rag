"""SQLAlchemy model for conversation threads."""

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
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class ChatThreadStatus(StrEnum):
    """Lifecycle state of a conversation thread."""

    ACTIVE = "active"
    ARCHIVED = "archived"


class ChatSubject(StrEnum):
    """Business subject of a conversation thread."""

    POLICY = "policy"
    ORDER = "order"
    REFUND = "refund"
    MEMBERSHIP = "membership"
    GENERAL = "general"


class ChatThread(Base):
    """A conversation context owned by one user."""

    __tablename__ = "chat_threads"
    __table_args__ = (
        Index(
            "ix_chat_threads_user_id_status",
            "user_id",
            "status",
        ),
        Index(
            "ix_chat_threads_last_message_at",
            "last_message_at",
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
            ondelete="RESTRICT",
        ),
        nullable=False,
    )

    title: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    status: Mapped[ChatThreadStatus] = mapped_column(
        Enum(
            ChatThreadStatus,
            name="chat_thread_status",
            values_callable=lambda enum_class: [
                member.value for member in enum_class
            ],
        ),
        nullable=False,
        default=ChatThreadStatus.ACTIVE,
        server_default=text("'active'"),
    )

    subject: Mapped[ChatSubject] = mapped_column(
        Enum(
            ChatSubject,
            name="chat_subject",
            values_callable=lambda enum_class: [
                member.value for member in enum_class
            ],
        ),
        nullable=False,
        default=ChatSubject.GENERAL,
        server_default=text("'general'"),
    )

    last_message_at: Mapped[datetime | None] = mapped_column(
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
        back_populates="chat_threads",
    )

    messages: Mapped[list["ChatMessage"]] = relationship(
        back_populates="thread",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="ChatMessage.sequence_number",
    )

    agent_runs: Mapped[list["AgentRun"]] = relationship(
        back_populates="thread",
        passive_deletes=True,
        order_by="AgentRun.created_at",
    )