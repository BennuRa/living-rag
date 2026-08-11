"""Prepare a complete, searchable Living RAG demonstration database.

This command is intentionally idempotent. It runs the existing business Seed
and sample-document ingestion commands, then applies the source-document
governance status and generates embeddings for all pending Chunks.

Run inside the API container:

    python scripts/prepare_demo_data.py
"""

from __future__ import annotations

import sys
from pathlib import Path

from sqlalchemy import select

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core.database import SessionLocal
from app.models.document import (
    DocumentGovernanceStatus,
    DocumentVersion,
)
from app.services.embedding_factory import create_embedding_provider
from app.services.embedding_service import embed_pending_chunks

if __package__:
    from .ingest_sample_documents import main as ingest_sample_documents
    from .seed_database import main as seed_database
else:
    # Keep ``python scripts/prepare_demo_data.py`` working from the API root.
    from ingest_sample_documents import main as ingest_sample_documents
    from seed_database import main as seed_database


SOURCE_STATUS_TO_GOVERNANCE_STATUS = {
    "active": DocumentGovernanceStatus.ACTIVE,
    "archived": DocumentGovernanceStatus.SUPERSEDED,
    "invalid": DocumentGovernanceStatus.INVALID,
}


def apply_sample_governance_statuses() -> int:
    """Map validated sample-document statuses to searchable governance states."""

    changed_count = 0

    with SessionLocal() as session:
        with session.begin():
            versions = session.scalars(
                select(DocumentVersion).order_by(
                    DocumentVersion.document_id,
                    DocumentVersion.version_number,
                )
            ).all()

            for version in versions:
                source_status = str(
                    (version.metadata_ or {}).get("source_document_status", "")
                ).lower()
                target_status = SOURCE_STATUS_TO_GOVERNANCE_STATUS.get(source_status)

                if target_status is None or version.governance_status == target_status:
                    continue

                version.governance_status = target_status
                changed_count += 1

    return changed_count


def synchronize_sample_policy_keys() -> int:
    """Copy the ingestion document key into the indexed policy key column."""

    changed_count = 0

    with SessionLocal() as session:
        with session.begin():
            versions = session.scalars(
                select(DocumentVersion).order_by(DocumentVersion.document_id)
            ).all()

            seen_documents: set[object] = set()

            for version in versions:
                document = version.document
                if document.id in seen_documents:
                    continue

                document_key = str(
                    (document.metadata_ or {}).get("document_key", "")
                ).strip()

                if document_key and document.policy_key != document_key:
                    document.policy_key = document_key
                    changed_count += 1

                seen_documents.add(document.id)

    return changed_count


def generate_pending_embeddings() -> int:
    """Generate and persist embeddings for every Chunk without a vector."""

    provider = create_embedding_provider()

    with SessionLocal() as session:
        with session.begin():
            return embed_pending_chunks(session, provider)


def main() -> None:
    """Run all idempotent demo-data preparation stages."""

    seed_database()
    ingest_sample_documents()
    changed_count = apply_sample_governance_statuses()
    policy_keys_synchronized = synchronize_sample_policy_keys()
    embedded_count = generate_pending_embeddings()

    print(
        "Demo data preparation completed: "
        f"governance_statuses_changed={changed_count}, "
        f"policy_keys_synchronized={policy_keys_synchronized}, "
        f"embeddings_created={embedded_count}."
    )


if __name__ == "__main__":
    main()
