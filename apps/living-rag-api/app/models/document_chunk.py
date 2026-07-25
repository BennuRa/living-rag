"""SQLAlchemy model for version-bound document chunks."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    CheckConstraint,
    DateTime,
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


class DocumentChunk(Base):
    """A searchable text chunk produced from one document version."""

    __tablename__ = "document_chunks"
    __table_args__ = (
        CheckConstraint(
            "chunk_index >= 0",
            name="ck_document_chunks_chunk_index_non_negative",
        ),
        CheckConstraint(
            "length(regexp_replace(content, '[[:space:]]', '', 'g')) > 0",
            name="ck_document_chunks_content_not_blank",
        ),
        UniqueConstraint(
            "document_version_id",
            "chunk_index",
            name="uq_document_chunks_version_id_chunk_index",
        ),
        Index(
            "ix_document_chunks_document_version_id_chunk_index",
            "document_version_id",
            "chunk_index",
        ),
        Index(
            "ix_document_chunks_content_hash",
            "content_hash",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    document_version_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey(
            "document_versions.id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )

    chunk_index: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    content_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )

    embedding: Mapped[list[float] | None] = mapped_column(
        Vector(768),
        nullable=True,
    )

    char_start: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    char_end: Mapped[int | None] = mapped_column(
        Integer,
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

    document_version: Mapped["DocumentVersion"] = relationship(
        back_populates="chunks",
    )