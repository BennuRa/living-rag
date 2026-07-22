"""backfill document version supersedes links

Revision ID: d91e3b7c5a20
Revises: f2c8d5a71b04
Create Date: 2026-07-20

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "d91e3b7c5a20"
down_revision: Union[str, Sequence[str], None] = "f2c8d5a71b04"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Link each sequential version to the version it supersedes."""

    op.execute(
        """
        WITH version_chain AS (
            SELECT
                id,
                LAG(id) OVER (
                    PARTITION BY document_id
                    ORDER BY version_number
                ) AS previous_version_id
            FROM document_versions
        )
        UPDATE document_versions AS current_version
        SET supersedes_version_id = version_chain.previous_version_id
        FROM version_chain
        WHERE current_version.id = version_chain.id
          AND current_version.supersedes_version_id IS NULL
          AND version_chain.previous_version_id IS NOT NULL
        """
    )


def downgrade() -> None:
    """Remove only the sequential links created by this migration."""

    op.execute(
        """
        WITH version_chain AS (
            SELECT
                id,
                LAG(id) OVER (
                    PARTITION BY document_id
                    ORDER BY version_number
                ) AS previous_version_id
            FROM document_versions
        )
        UPDATE document_versions AS current_version
        SET supersedes_version_id = NULL
        FROM version_chain
        WHERE current_version.id = version_chain.id
          AND current_version.supersedes_version_id = version_chain.previous_version_id
          AND version_chain.previous_version_id IS NOT NULL
        """
    )