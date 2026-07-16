"""add orders and refund requests

Revision ID: f9e3f7a938ad
Revises: 9e7f87036215
Create Date: 2026-07-16 08:34:57.797699

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "f9e3f7a938ad"
down_revision: Union[str, Sequence[str], None] = "9e7f87036215"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""

    op.create_table(
        "orders",
        sa.Column(
            "id",
            sa.UUID(),
            nullable=False,
        ),
        sa.Column(
            "membership_account_id",
            sa.UUID(),
            nullable=False,
        ),
        sa.Column(
            "order_number",
            sa.String(length=64),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum(
                "pending",
                "paid",
                "shipped",
                "completed",
                "cancelled",
                "refunded",
                "partially_refunded",
                name="order_status",
            ),
            server_default=sa.text("'pending'"),
            nullable=False,
        ),
        sa.Column(
            "total_amount",
            sa.Numeric(precision=12, scale=2),
            nullable=False,
        ),
        sa.Column(
            "currency",
            sa.String(length=3),
            server_default=sa.text("'CNY'"),
            nullable=False,
        ),
        sa.Column(
            "ordered_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "paid_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "completed_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
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
            "total_amount >= 0",
            name="ck_orders_total_amount_non_negative",
        ),
        sa.ForeignKeyConstraint(
            ["membership_account_id"],
            ["membership_accounts.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "order_number",
            name="uq_orders_order_number",
        ),
    )

    op.create_index(
        "ix_orders_membership_account_id_status",
        "orders",
        ["membership_account_id", "status"],
        unique=False,
    )

    op.create_index(
        "ix_orders_ordered_at",
        "orders",
        ["ordered_at"],
        unique=False,
    )

    op.create_table(
        "refund_requests",
        sa.Column(
            "id",
            sa.UUID(),
            nullable=False,
        ),
        sa.Column(
            "order_id",
            sa.UUID(),
            nullable=False,
        ),
        sa.Column(
            "request_number",
            sa.String(length=64),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum(
                "pending",
                "reviewing",
                "approved",
                "rejected",
                "processing",
                "completed",
                "cancelled",
                name="refund_request_status",
            ),
            server_default=sa.text("'pending'"),
            nullable=False,
        ),
        sa.Column(
            "requested_amount",
            sa.Numeric(precision=12, scale=2),
            nullable=False,
        ),
        sa.Column(
            "approved_amount",
            sa.Numeric(precision=12, scale=2),
            nullable=True,
        ),
        sa.Column(
            "reason",
            sa.Text(),
            nullable=False,
        ),
        sa.Column(
            "rejection_reason",
            sa.Text(),
            nullable=True,
        ),
        sa.Column(
            "requested_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "reviewed_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "completed_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
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
            "approved_amount IS NULL OR approved_amount <= requested_amount",
            name="ck_refund_requests_approved_amount_lte_requested",
        ),
        sa.CheckConstraint(
            "approved_amount IS NULL OR approved_amount > 0",
            name="ck_refund_requests_approved_amount_positive",
        ),
        sa.CheckConstraint(
            "requested_amount > 0",
            name="ck_refund_requests_requested_amount_positive",
        ),
        sa.ForeignKeyConstraint(
            ["order_id"],
            ["orders.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "request_number",
            name="uq_refund_requests_request_number",
        ),
    )

    op.create_index(
        "ix_refund_requests_order_id_status",
        "refund_requests",
        ["order_id", "status"],
        unique=False,
    )

    op.create_index(
        "ix_refund_requests_requested_at",
        "refund_requests",
        ["requested_at"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""

    op.drop_index(
        "ix_refund_requests_requested_at",
        table_name="refund_requests",
    )
    op.drop_index(
        "ix_refund_requests_order_id_status",
        table_name="refund_requests",
    )
    op.drop_table("refund_requests")

    op.drop_index(
        "ix_orders_ordered_at",
        table_name="orders",
    )
    op.drop_index(
        "ix_orders_membership_account_id_status",
        table_name="orders",
    )
    op.drop_table("orders")

    op.execute(
        "DROP TYPE IF EXISTS refund_request_status"
    )
    op.execute(
        "DROP TYPE IF EXISTS order_status"
    )