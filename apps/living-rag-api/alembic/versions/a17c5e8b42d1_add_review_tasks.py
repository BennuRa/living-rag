"""Create review_tasks table."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "a17c5e8b42d1"
down_revision: Union[str, None] = "d8a4f6b921c7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create the review_tasks table and supporting indexes."""

    op.create_table(
        "review_tasks",
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
            "task_type",
            sa.String(length=64),
            server_default=sa.text("'resolve_conflict'"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(length=32),
            server_default=sa.text("'pending'"),
            nullable=False,
        ),
        sa.Column(
            "assigned_to",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        sa.Column(
            "decision",
            sa.String(length=32),
            nullable=True,
        ),
        sa.Column(
            "decision_reason",
            sa.Text(),
            nullable=True,
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
        sa.Column(
            "resolved_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(
            ["conflict_id"],
            ["conflicts.id"],
            name="fk_review_tasks_conflict_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        "ix_review_tasks_status",
        "review_tasks",
        ["status"],
        unique=False,
    )

    op.create_index(
        "ix_review_tasks_conflict_id",
        "review_tasks",
        ["conflict_id"],
        unique=False,
    )


def downgrade() -> None:
    """Drop the review_tasks table and supporting indexes."""

    op.drop_index(
        "ix_review_tasks_conflict_id",
        table_name="review_tasks",
    )

    op.drop_index(
        "ix_review_tasks_status",
        table_name="review_tasks",
    )

    op.drop_table("review_tasks")