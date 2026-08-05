"""Tests for current and historical pgvector retrieval."""

from datetime import UTC, datetime

from app.models.document import (
    Document,
    DocumentGovernanceStatus,
    DocumentSourceType,
    DocumentVersion,
    DocumentVersionStatus,
)
from app.models.document_chunk import DocumentChunk
from app.services.document_ingestion import compute_content_hash
from app.services.retrieval import search_similar_chunks


TEST_EMBEDDING = [1.0, *([0.0] * 767)]


def _create_version_with_chunk(
    *,
    db_session,
    document: Document,
    version_number: int,
    effective_at: datetime,
    governance_status: DocumentGovernanceStatus,
    supersedes_version_id=None,
) -> DocumentVersion:
    """Create one ready document version and one searchable Chunk."""

    content = f"退款政策第 {version_number} 版。"

    version = DocumentVersion(
        document=document,
        version_number=version_number,
        status=DocumentVersionStatus.READY,
        source_type=DocumentSourceType.OFFICIAL_POLICY,
        governance_status=governance_status,
        effective_at=effective_at,
        expires_at=None,
        supersedes_version_id=supersedes_version_id,
        content=content,
        content_hash=compute_content_hash(content),
    )
    db_session.add(version)
    db_session.flush()

    chunk = DocumentChunk(
        document_version=version,
        chunk_index=0,
        content=content,
        content_hash=compute_content_hash(content),
        embedding=TEST_EMBEDDING,
    )
    db_session.add(chunk)
    db_session.flush()

    return version


def test_search_similar_chunks_uses_correct_version_for_current_and_history(
    db_session,
) -> None:
    """Current retrieval returns v3; historical retrieval returns v1 or v2."""

    document = Document(
        title="历史退款政策",
        policy_key="HISTORICAL-REFUND-POLICY",
        domain="refund",
    )
    db_session.add(document)
    db_session.flush()

    version_1 = _create_version_with_chunk(
        db_session=db_session,
        document=document,
        version_number=1,
        effective_at=datetime(2025, 1, 1, tzinfo=UTC),
        governance_status=DocumentGovernanceStatus.SUPERSEDED,
    )
    version_2 = _create_version_with_chunk(
        db_session=db_session,
        document=document,
        version_number=2,
        effective_at=datetime(2025, 4, 1, tzinfo=UTC),
        governance_status=DocumentGovernanceStatus.SUPERSEDED,
        supersedes_version_id=version_1.id,
    )
    version_3 = _create_version_with_chunk(
        db_session=db_session,
        document=document,
        version_number=3,
        effective_at=datetime(2025, 7, 1, tzinfo=UTC),
        governance_status=DocumentGovernanceStatus.ACTIVE,
        supersedes_version_id=version_2.id,
    )

    current_results = search_similar_chunks(
        db_session,
        TEST_EMBEDDING,
        query_text="退款政策",
        now=datetime(2025, 8, 1, tzinfo=UTC),
    )
    february_results = search_similar_chunks(
        db_session,
        TEST_EMBEDDING,
        query_text="退款政策",
        as_of_date=datetime(2025, 2, 1, tzinfo=UTC),
    )
    may_results = search_similar_chunks(
        db_session,
        TEST_EMBEDDING,
        query_text="退款政策",
        as_of_date=datetime(2025, 5, 1, tzinfo=UTC),
    )
    august_results = search_similar_chunks(
        db_session,
        TEST_EMBEDDING,
        query_text="退款政策",
        as_of_date=datetime(2025, 8, 1, tzinfo=UTC),
    )

    assert [result[1].id for result in current_results] == [version_3.id]
    assert [result[1].id for result in february_results] == [version_1.id]
    assert [result[1].id for result in may_results] == [version_2.id]
    assert [result[1].id for result in august_results] == [version_3.id]


def test_refund_retrieval_keeps_a_relevant_faq_for_conflict_governance(
    db_session,
) -> None:
    """Refund retrieval keeps an FAQ candidate alongside official policy."""

    official_document = Document(
        title="Official refund policy",
        policy_key="REFUND-POLICY",
    )
    faq_document = Document(
        title="Refund FAQ",
        policy_key="REFUND-FAQ-001",
    )
    db_session.add_all([official_document, faq_document])
    db_session.flush()

    official_version = _create_version_with_chunk(
        db_session=db_session,
        document=official_document,
        version_number=3,
        effective_at=datetime(2025, 7, 1, tzinfo=UTC),
        governance_status=DocumentGovernanceStatus.ACTIVE,
    )

    faq_content = "FAQ: all members may request a refund within 30 days."
    faq_version = DocumentVersion(
        document=faq_document,
        version_number=1,
        status=DocumentVersionStatus.READY,
        source_type=DocumentSourceType.FAQ,
        governance_status=DocumentGovernanceStatus.ACTIVE,
        effective_at=datetime(2025, 7, 5, tzinfo=UTC),
        content=faq_content,
        content_hash=compute_content_hash(faq_content),
    )
    db_session.add(faq_version)
    db_session.flush()

    db_session.add(
        DocumentChunk(
            document_version=faq_version,
            chunk_index=0,
            content=faq_content,
            content_hash=compute_content_hash(faq_content),
            embedding=TEST_EMBEDDING,
        ),
    )
    db_session.flush()

    results = search_similar_chunks(
        db_session,
        TEST_EMBEDDING,
        query_text="所有会员可以在 30 天内退款吗？",
        limit=2,
        now=datetime(2025, 8, 1, tzinfo=UTC),
    )

    result_version_ids = {row[1].id for row in results}

    assert official_version.id in result_version_ids
    assert faq_version.id in result_version_ids
