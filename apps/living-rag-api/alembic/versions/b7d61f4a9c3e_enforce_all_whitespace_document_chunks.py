"""enforce all whitespace document chunks

Revision ID: b7d61f4a9c3e
Revises: 72835e40a398
Create Date: 2026-07-19

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "b7d61f4a9c3e"
down_revision: Union[str, Sequence[str], None] = "72835e40a398"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Reject document chunks that contain only any kind of whitespace."""

    op.drop_constraint(
        "ck_document_chunks_content_not_blank",
        "document_chunks",
        type_="check",
    )
    op.create_check_constraint(
        "ck_document_chunks_content_not_blank",
        "document_chunks",
        "length(regexp_replace(content, '[[:space:]]', '', 'g')) > 0",
    )


def downgrade() -> None:
    """Restore the original trim-based document chunk content check."""

    op.drop_constraint(
        "ck_document_chunks_content_not_blank",
        "document_chunks",
        type_="check",
    )
    op.create_check_constraint(
        "ck_document_chunks_content_not_blank",
        "document_chunks",
        "length(trim(content)) > 0",
    )