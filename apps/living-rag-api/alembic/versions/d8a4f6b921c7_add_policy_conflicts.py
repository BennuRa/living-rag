"""Create policy conflicts and conflict evidences tables."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "d8a4f6b921c7"
down_revision: Union[str, None] = "c4d9a8e71f10"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create conflicts and conflict_evidences tables."""

    op.create_table(
        "conflicts",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "kind",
            sa.String(length=64),
            nullable=False,
        ),
        sa.Column(
            "severity",
            sa.String(length=32),
            nullable=False,
        ),
        sa.Column(
            "rule_key",
            sa.String(length=128),
            nullable=False,
        ),
        sa.Column(
            "left_rule_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        sa.Column(
            "right_rule_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        sa.Column(
            "left_document_version_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "right_document_version_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "reason",
            sa.Text(),
            nullable=False,
        ),
        sa.Column(
            "recommended_action",
            sa.Text(),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(length=32),
            server_default=sa.text("'open'"),
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
        sa.ForeignKeyConstraint(
            ["left_rule_id"],
            ["policy_rules.id"],
            name="fk_conflicts_left_rule_id",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["right_rule_id"],
            ["policy_rules.id"],
            name="fk_conflicts_right_rule_id",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["left_document_version_id"],
            ["document_versions.id"],
            name="fk_conflicts_left_document_version_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["right_document_version_id"],
            ["document_versions.id"],
            name="fk_conflicts_right_document_version_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        "ix_conflicts_rule_key",
        "conflicts",
        ["rule_key"],
        unique=False,
    )

    op.create_index(
        "ix_conflicts_status",
        "conflicts",
        ["status"],
        unique=False,
    )

    op.create_index(
        "ix_conflicts_left_document_version_id",
        "conflicts",
        ["left_document_version_id"],
        unique=False,
    )

    op.create_index(
        "ix_conflicts_right_document_version_id",
        "conflicts",
        ["right_document_version_id"],
        unique=False,
    )

    op.create_table(
        "conflict_evidences",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "conflict_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "rule_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        sa.Column(
            "document_version_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "quote",
            sa.Text(),
            nullable=False,
        ),
        sa.Column(
            "position",
            sa.Integer(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["conflict_id"],
            ["conflicts.id"],
            name="fk_conflict_evidences_conflict_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["rule_id"],
            ["policy_rules.id"],
            name="fk_conflict_evidences_rule_id",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["document_version_id"],
            ["document_versions.id"],
            name="fk_conflict_evidences_document_version_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        "ix_conflict_evidences_conflict_id",
        "conflict_evidences",
        ["conflict_id"],
        unique=False,
    )

    op.create_index(
        "ix_conflict_evidences_document_version_id",
        "conflict_evidences",
        ["document_version_id"],
        unique=False,
    )


def downgrade() -> None:
    """Drop conflict evidence and conflict tables."""

    op.drop_index(
        "ix_conflict_evidences_document_version_id",
        table_name="conflict_evidences",
    )

    op.drop_index(
        "ix_conflict_evidences_conflict_id",
        table_name="conflict_evidences",
    )

    op.drop_table("conflict_evidences")

    op.drop_index(
        "ix_conflicts_right_document_version_id",
        table_name="conflicts",
    )

    op.drop_index(
        "ix_conflicts_left_document_version_id",
        table_name="conflicts",
    )

    op.drop_index(
        "ix_conflicts_status",
        table_name="conflicts",
    )

    op.drop_index(
        "ix_conflicts_rule_key",
        table_name="conflicts",
    )

    op.drop_table("conflicts")