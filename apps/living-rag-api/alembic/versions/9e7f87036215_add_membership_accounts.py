"""add membership accounts

Revision ID: 9e7f87036215
Revises: 07769ae36e73
Create Date: 2026-07-16 06:03:52.070937

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "9e7f87036215"
down_revision: Union[str, Sequence[str], None] = "07769ae36e73"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""

    op.create_table(
        "membership_accounts",
        sa.Column(
            "id",
            sa.UUID(),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.UUID(),
            nullable=False,
        ),
        sa.Column(
            "membership_number",
            sa.String(length=64),
            nullable=False,
        ),
        sa.Column(
            "tier",
            sa.Enum(
                "standard",
                "silver",
                "gold",
                "platinum",
                name="membership_tier",
            ),
            server_default=sa.text("'standard'"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum(
                "active",
                "suspended",
                "expired",
                "closed",
                name="membership_account_status",
            ),
            server_default=sa.text("'active'"),
            nullable=False,
        ),
        sa.Column(
            "points",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "expires_at",
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
            "points >= 0",
            name="ck_membership_accounts_points_non_negative",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "membership_number",
            name="uq_membership_accounts_membership_number",
        ),
        sa.UniqueConstraint(
            "user_id",
            name="uq_membership_accounts_user_id",
        ),
    )

    op.create_index(
        "ix_membership_accounts_status_created_at",
        "membership_accounts",
        ["status", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""

    op.drop_index(
        "ix_membership_accounts_status_created_at",
        table_name="membership_accounts",
    )
    op.drop_table("membership_accounts")
    op.execute(
        "DROP TYPE IF EXISTS membership_account_status"
    )
    op.execute(
        "DROP TYPE IF EXISTS membership_tier"
    )