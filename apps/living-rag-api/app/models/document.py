"""SQLAlchemy models for stable documents and their versioned content snapshots."""

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


class DocumentStatus(StrEnum):
    """Lifecycle state of a stable logical document."""

    ACTIVE = "active"
    ARCHIVED = "archived"


class DocumentVersionStatus(StrEnum):
    """Technical processing lifecycle state of one document content snapshot."""

    PENDING = "pending"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"


class DocumentSourceType(StrEnum):
    """Business authority category of one source document version."""

    OFFICIAL_POLICY = "official_policy"
    TEMPORARY_NOTICE = "temporary_notice"
    FAQ = "faq"
    OPERATION_NOTICE = "operation_notice"


class DocumentGovernanceStatus(StrEnum):
    """Business governance state that controls whether a version may be used."""

    DRAFT = "draft"
    PENDING_REVIEW = "pending_review"
    ACTIVE = "active"
    SUPERSEDED = "superseded"
    EXPIRED = "expired"
    INVALID = "invalid"


class Document(Base):
    """A stable logical document independent of its individual content versions."""

    __tablename__ = "documents"
    __table_args__ = (
        UniqueConstraint(
            "policy_key",
            name="uq_documents_policy_key",
        ),
        Index(
            "ix_documents_status_created_at",
            "status",
            "created_at",
        ),
        Index(
            "ix_documents_domain_status",
            "domain",
            "status",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    policy_key: Mapped[str | None] = mapped_column(
        String(128),
        nullable=True,
    )

    domain: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )

    status: Mapped[DocumentStatus] = mapped_column(
        Enum(
            DocumentStatus,
            name="document_status",
            values_callable=lambda enum_class: [
                member.value for member in enum_class
            ],
        ),
        nullable=False,
        default=DocumentStatus.ACTIVE,
        server_default=text("'active'"),
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

    versions: Mapped[list["DocumentVersion"]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="DocumentVersion.version_number",
    )


class DocumentVersion(Base):
    """A traceable, immutable-in-intent content snapshot of one document."""

    __tablename__ = "document_versions"
    __table_args__ = (
        CheckConstraint(
            "version_number > 0",
            name="ck_document_versions_version_number_positive",
        ),
        CheckConstraint(
            "expires_at IS NULL OR effective_at IS NULL OR expires_at > effective_at",
            name="ck_document_versions_expiry_after_effective_at",
        ),
        UniqueConstraint(
            "document_id",
            "version_number",
            name="uq_document_versions_document_id_version_number",
        ),
        Index(
            "ix_document_versions_document_id_status",
            "document_id",
            "status",
        ),
        Index(
            "ix_document_versions_governance_status_effective_at",
            "governance_status",
            "effective_at",
        ),
        Index(
            "ix_document_versions_content_hash",
            "content_hash",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    document_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey(
            "documents.id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )

    version_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    status: Mapped[DocumentVersionStatus] = mapped_column(
        Enum(
            DocumentVersionStatus,
            name="document_version_status",
            values_callable=lambda enum_class: [
                member.value for member in enum_class
            ],
        ),
        nullable=False,
        default=DocumentVersionStatus.PENDING,
        server_default=text("'pending'"),
    )

    source_type: Mapped[DocumentSourceType] = mapped_column(
        Enum(
            DocumentSourceType,
            name="document_source_type",
            values_callable=lambda enum_class: [
                member.value for member in enum_class
            ],
        ),
        nullable=False,
        default=DocumentSourceType.OFFICIAL_POLICY,
        server_default=text("'official_policy'"),
    )

    governance_status: Mapped[DocumentGovernanceStatus] = mapped_column(
        Enum(
            DocumentGovernanceStatus,
            name="document_governance_status",
            values_callable=lambda enum_class: [
                member.value for member in enum_class
            ],
        ),
        nullable=False,
        default=DocumentGovernanceStatus.DRAFT,
        server_default=text("'draft'"),
    )

    effective_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    supersedes_version_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey(
            "document_versions.id",
            ondelete="SET NULL",
        ),
        nullable=True,
    )

    original_filename: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    content_type: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    content_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
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

    document: Mapped["Document"] = relationship(
        back_populates="versions",
        foreign_keys=[document_id],
    )

    supersedes_version: Mapped["DocumentVersion | None"] = relationship(
        back_populates="superseded_by_versions",
        foreign_keys=[supersedes_version_id],
        remote_side="DocumentVersion.id",
    )

    superseded_by_versions: Mapped[list["DocumentVersion"]] = relationship(
        back_populates="supersedes_version",
        foreign_keys=[supersedes_version_id],
    )

    chunks: Mapped[list["DocumentChunk"]] = relationship(
        back_populates="document_version",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="DocumentChunk.chunk_index",
    )