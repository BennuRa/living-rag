"""Create approval_tasks table."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "21f0e8383e69"
down_revision: Union[str, Sequence[str], None] = "a17c5e8b42d1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create the approval_tasks table and supporting indexes."""

    op.create_table(
        "approval_tasks",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "task_type",
            sa.Enum(
                "refund_request",
                "direct_refund",
                "modify_policy",
                "delete_document",
                name="approval_task_type",
            ),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum(
                "pending",
                "approved",
                "rejected",
                "cancelled",
                name="approval_task_status",
            ),
            server_default=sa.text("'pending'"),
            nullable=False,
        ),
        sa.Column(
            "refund_request_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        sa.Column(
            "resource_type",
            sa.String(length=64),
            nullable=False,
        ),
        sa.Column(
            "resource_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        sa.Column(
            "requested_by",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        sa.Column(
            "trace_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        sa.Column(
            "reason",
            sa.Text(),
            nullable=False,
        ),
        sa.Column(
            "decision",
            sa.Enum(
                "approve",
                "reject",
                name="approval_decision",
            ),
            nullable=True,
        ),
        sa.Column(
            "decision_reason",
            sa.Text(),
            nullable=True,
        ),
        sa.Column(
            "decided_by",
            postgresql.UUID(as_uuid=True),
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
            "decided_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["refund_request_id"],
            ["refund_requests.id"],
            name="fk_approval_tasks_refund_request_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["requested_by"],
            ["users.id"],
            name="fk_approval_tasks_requested_by",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["decided_by"],
            ["users.id"],
            name="fk_approval_tasks_decided_by",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        "ix_approval_tasks_status",
        "approval_tasks",
        ["status"],
        unique=False,
    )

    op.create_index(
        "ix_approval_tasks_task_type",
        "approval_tasks",
        ["task_type"],
        unique=False,
    )

    op.create_index(
        "ix_approval_tasks_resource_type_resource_id",
        "approval_tasks",
        ["resource_type", "resource_id"],
        unique=False,
    )

    op.create_index(
        "ix_approval_tasks_trace_id",
        "approval_tasks",
        ["trace_id"],
        unique=False,
    )


def downgrade() -> None:
    """Drop the approval_tasks table and supporting database objects."""

    op.drop_index(
        "ix_approval_tasks_trace_id",
        table_name="approval_tasks",
    )

    op.drop_index(
        "ix_approval_tasks_resource_type_resource_id",
        table_name="approval_tasks",
    )

    op.drop_index(
        "ix_approval_tasks_task_type",
        table_name="approval_tasks",
    )

    op.drop_index(
        "ix_approval_tasks_status",
        table_name="approval_tasks",
    )

    op.drop_table("approval_tasks")

    op.execute(
        "DROP TYPE IF EXISTS approval_decision"
    )
    op.execute(
        "DROP TYPE IF EXISTS approval_task_status"
    )
    op.execute(
        "DROP TYPE IF EXISTS approval_task_type"
    )