"""add embedding to document chunks

Revision ID: b6253fb946c2
Revises: d91e3b7c5a20
Create Date: 2026-07-23 05:55:47.251696

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

# revision identifiers, used by Alembic.
revision: str = "b6253fb946c2"
down_revision: Union[str, Sequence[str], None] = "d91e3b7c5a20"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.add_column(
        "document_chunks",
        sa.Column(
            "embedding",
            Vector(768),
            nullable=True,
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("document_chunks", "embedding")