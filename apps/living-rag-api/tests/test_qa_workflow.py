"""Tests for the structured Living RAG QA workflow."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.models.document import (
    DocumentGovernanceStatus,
    DocumentSourceType,
)
from app.schemas.retrieval import RetrievalResult
from app.services.citation_validation import (
    build_citations_from_answer,
    validate_answer_citations,
)
from app.services.llm import MockLLMProvider


def make_retrieval_result(
    *,
    governance_status: DocumentGovernanceStatus = DocumentGovernanceStatus.ACTIVE,
    effective_at: datetime | None = None,
    expires_at: datetime | None = None,
    content: str = "Refunds are available within 15 days.",
    similarity: float = 0.85,
) -> RetrievalResult:
    """Build one deterministic retrieval result for unit tests."""

    now = datetime.now(UTC)

    return RetrievalResult(
        document_id=uuid4(),
        document_version_id=uuid4(),
        chunk_id=uuid4(),
        document_title="Refund Policy",
        version_number=3,
        source_type=DocumentSourceType.OFFICIAL_POLICY,
        governance_status=governance_status,
        effective_at=effective_at or now - timedelta(days=1),
        expires_at=expires_at,
        content=content,
        similarity=similarity,
    )


def test_mock_llm_returns_structured_answer_with_evidence() -> None:
    """A grounded answer contains conditions, citation indices, and confidence."""

    provider = MockLLMProvider()

    draft = provider.generate_answer(
        question="What is the refund window?",
        context="Refund Policy version 3: refunds are available within 15 days.",
    )

    assert draft.answer
    assert draft.conditions
    assert draft.citation_indices == [1]
    assert draft.confidence == 0.85
    assert draft.limitations == []


def test_mock_llm_returns_safe_structured_answer_without_evidence() -> None:
    """An empty context produces a conservative answer without citations."""

    provider = MockLLMProvider()

    draft = provider.generate_answer(
        question="What is the refund window?",
        context="",
    )

    assert draft.answer == (
        "I do not have enough grounded evidence "
        "to answer this question."
    )
    assert draft.conditions == []
    assert draft.citation_indices == []
    assert draft.confidence == 0.0
    assert draft.limitations


def test_validate_active_current_citation() -> None:
    """An active, effective, non-expired citation is valid."""

    result = make_retrieval_result()

    assert validate_answer_citations(
        "The answer is supported by [1].",
        [result],
        [1],
    )


@pytest.mark.parametrize(
    "result",
    [
        make_retrieval_result(
            governance_status=DocumentGovernanceStatus.INVALID,
        ),
        make_retrieval_result(
            effective_at=datetime.now(UTC) + timedelta(days=1),
        ),
        make_retrieval_result(
            expires_at=datetime.now(UTC) - timedelta(seconds=1),
        ),
        make_retrieval_result(
            content="   ",
        ),
    ],
)
def test_reject_invalid_citation_evidence(
    result: RetrievalResult,
) -> None:
    """Invalid status, timing, or blank content must reject a citation."""

    assert not validate_answer_citations(
        "The answer is supported by [1].",
        [result],
        [1],
    )


def test_reject_out_of_range_citation() -> None:
    """A citation index outside the result list must be rejected."""

    result = make_retrieval_result()

    assert not validate_answer_citations(
        "The answer is supported by [2].",
        [result],
        [2],
    )


def test_reject_mismatched_text_and_structured_citations() -> None:
    """Textual markers and structured citation indices must agree."""

    result = make_retrieval_result()

    assert not validate_answer_citations(
        "The answer is supported by [1].",
        [result],
        [2],
    )


def test_build_citation_from_structured_index() -> None:
    """A valid structured index maps to the real retrieval result."""

    result = make_retrieval_result()

    citations = build_citations_from_answer(
        "The answer is supported by [1].",
        [result],
        [1],
    )

    assert len(citations) == 1
    assert citations[0].document_id == result.document_id
    assert citations[0].document_version_id == result.document_version_id
    assert citations[0].chunk_id == result.chunk_id
    assert citations[0].quote == result.content
    assert citations[0].relevance_score == result.similarity