"""add document governance fields

Revision ID: f2c8d5a71b04
Revises: b7d61f4a9c3e
Create Date: 2026-07-20

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "f2c8d5a71b04"
down_revision: Union[str, Sequence[str], None] = "b7d61f4a9c3e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


document_source_type = postgresql.ENUM(
    "official_policy",
    "temporary_notice",
    "faq",
    "operation_notice",
    name="document_source_type",
    create_type=False,
)

document_governance_status = postgresql.ENUM(
    "draft",
    "pending_review",
    "active",
    "superseded",
    "expired",
    "invalid",
    name="document_governance_status",
    create_type=False,
)


def upgrade() -> None:
    """Add structured governance fields and backfill existing Day 3 data."""

    bind = op.get_bind()
    document_source_type.create(bind, checkfirst=True)
    document_governance_status.create(bind, checkfirst=True)

    op.add_column(
        "documents",
        sa.Column(
            "policy_key",
            sa.String(length=128),
            nullable=True,
        ),
    )
    op.add_column(
        "documents",
        sa.Column(
            "domain",
            sa.String(length=64),
            nullable=True,
        ),
    )

    op.add_column(
        "document_versions",
        sa.Column(
            "source_type",
            document_source_type,
            nullable=False,
            server_default=sa.text("'official_policy'"),
        ),
    )
    op.add_column(
        "document_versions",
        sa.Column(
            "governance_status",
            document_governance_status,
            nullable=False,
            server_default=sa.text("'draft'"),
        ),
    )
    op.add_column(
        "document_versions",
        sa.Column(
            "effective_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.add_column(
        "document_versions",
        sa.Column(
            "expires_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.add_column(
        "document_versions",
        sa.Column(
            "supersedes_version_id",
            sa.UUID(),
            nullable=True,
        ),
    )
    op.add_column(
        "document_versions",
        sa.Column(
            "original_filename",
            sa.String(length=255),
            nullable=True,
        ),
    )
    op.add_column(
        "document_versions",
        sa.Column(
            "content_type",
            sa.String(length=100),
            nullable=True,
        ),
    )

    op.execute(
        """
        UPDATE documents
        SET policy_key = COALESCE(
            metadata ->> 'document_key',
            'DOCUMENT-' || id::text
        )
        """
    )

    op.execute(
        """
        UPDATE documents
        SET domain = CASE
            WHEN policy_key LIKE '%REFUND%' THEN 'refund'
            WHEN policy_key LIKE '%MEMBERSHIP%' THEN 'membership'
            WHEN policy_key LIKE '%DELIVERY%' THEN 'delivery'
            WHEN policy_key LIKE '%DOUBLE-11%' THEN 'refund'
            WHEN policy_key LIKE '%INVALID%' THEN 'refund'
            ELSE 'general'
        END
        """
    )

    op.execute(
        """
        UPDATE document_versions
        SET source_type = (
            CASE metadata ->> 'document_type'
                WHEN '正式政策' THEN 'official_policy'
                WHEN 'FAQ' THEN 'faq'
                WHEN '临时活动公告' THEN 'temporary_notice'
                WHEN '错误公告' THEN 'operation_notice'
                ELSE 'official_policy'
            END
        )::document_source_type
        """
    )

    op.execute(
        """
        UPDATE document_versions
        SET governance_status = (
            CASE metadata ->> 'source_document_status'
                WHEN 'active' THEN 'active'
                WHEN 'archived' THEN 'superseded'
                WHEN 'invalid' THEN 'invalid'
                ELSE 'draft'
            END
        )::document_governance_status
        """
    )

    op.execute(
        """
        UPDATE document_versions
        SET effective_at = NULLIF(metadata ->> 'effective_at', '')::timestamptz,
            expires_at = NULLIF(metadata ->> 'expires_at', '')::timestamptz,
            original_filename = NULLIF(metadata ->> 'source_file', ''),
            content_type = 'text/markdown'
        """
    )

    op.execute(
        """
        UPDATE document_versions AS current_version
        SET supersedes_version_id = previous_version.id
        FROM document_versions AS previous_version
        WHERE current_version.document_id = previous_version.document_id
          AND current_version.version_number = previous_version.version_number + 1
        """
    )

    op.create_unique_constraint(
        "uq_documents_policy_key",
        "documents",
        ["policy_key"],
    )
    op.create_index(
        "ix_documents_domain_status",
        "documents",
        ["domain", "status"],
        unique=False,
    )
    op.create_check_constraint(
        "ck_document_versions_expiry_after_effective_at",
        "document_versions",
        "expires_at IS NULL OR effective_at IS NULL OR expires_at > effective_at",
    )
    op.create_foreign_key(
        "fk_document_versions_supersedes_version_id",
        "document_versions",
        "document_versions",
        ["supersedes_version_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_document_versions_governance_status_effective_at",
        "document_versions",
        ["governance_status", "effective_at"],
        unique=False,
    )


def downgrade() -> None:
    """Remove structured governance fields while preserving original JSONB metadata."""

    op.drop_index(
        "ix_document_versions_governance_status_effective_at",
        table_name="document_versions",
    )
    op.drop_constraint(
        "fk_document_versions_supersedes_version_id",
        "document_versions",
        type_="foreignkey",
    )
    op.drop_constraint(
        "ck_document_versions_expiry_after_effective_at",
        "document_versions",
        type_="check",
    )

    op.drop_column("document_versions", "content_type")
    op.drop_column("document_versions", "original_filename")
    op.drop_column("document_versions", "supersedes_version_id")
    op.drop_column("document_versions", "expires_at")
    op.drop_column("document_versions", "effective_at")
    op.drop_column("document_versions", "governance_status")
    op.drop_column("document_versions", "source_type")

    op.drop_index(
        "ix_documents_domain_status",
        table_name="documents",
    )
    op.drop_constraint(
        "uq_documents_policy_key",
        "documents",
        type_="unique",
    )
    op.drop_column("documents", "domain")
    op.drop_column("documents", "policy_key")

    bind = op.get_bind()
    document_governance_status.drop(bind, checkfirst=True)
    document_source_type.drop(bind, checkfirst=True)