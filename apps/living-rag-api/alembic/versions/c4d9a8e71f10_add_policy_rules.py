"""Create policy_rules table."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "c4d9a8e71f10"
down_revision: Union[str, None] = "b6253fb946c2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create the policy_rules table and supporting indexes."""

    op.create_table(
        "policy_rules",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "document_version_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "rule_key",
            sa.String(length=128),
            nullable=False,
        ),
        sa.Column(
            "value",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "conditions",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "source_quote",
            sa.Text(),
            nullable=False,
        ),
        sa.Column(
            "effective_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "expires_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "confidence",
            sa.Float(),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "confidence >= 0.0 AND confidence <= 1.0",
            name="ck_policy_rules_confidence_range",
        ),
        sa.ForeignKeyConstraint(
            ["document_version_id"],
            ["document_versions.id"],
            name="fk_policy_rules_document_version_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        "ix_policy_rules_document_version_id",
        "policy_rules",
        ["document_version_id"],
        unique=False,
    )

    op.create_index(
        "ix_policy_rules_rule_key",
        "policy_rules",
        ["rule_key"],
        unique=False,
    )

    op.create_index(
        "ix_policy_rules_effective_at",
        "policy_rules",
        ["effective_at"],
        unique=False,
    )


def downgrade() -> None:
    """Drop the policy_rules table and supporting indexes."""

    op.drop_index(
        "ix_policy_rules_effective_at",
        table_name="policy_rules",
    )

    op.drop_index(
        "ix_policy_rules_rule_key",
        table_name="policy_rules",
    )

    op.drop_index(
        "ix_policy_rules_document_version_id",
        table_name="policy_rules",
    )

    op.drop_table("policy_rules")