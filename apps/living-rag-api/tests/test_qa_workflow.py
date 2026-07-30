"""Living RAG 结构化问答工作流测试。"""

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
    content: str = "退款政策规定，退款期限为签收后的 15 天内。",
    similarity: float = 0.85,
) -> RetrievalResult:
    """构造一条用于测试的确定性检索结果。"""

    now = datetime.now(UTC)

    return RetrievalResult(
        document_id=uuid4(),
        document_version_id=uuid4(),
        chunk_id=uuid4(),
        document_title="退款政策",
        version_number=3,
        source_type=DocumentSourceType.OFFICIAL_POLICY,
        governance_status=governance_status,
        effective_at=effective_at or now - timedelta(days=1),
        expires_at=expires_at,
        content=content,
        similarity=similarity,
    )


def test_mock_llm_returns_structured_answer_with_evidence() -> None:
    """有证据时，回答应包含条件、引用编号和置信度。"""

    provider = MockLLMProvider()

    draft = provider.generate_answer(
        question="退款期限是多少？",
        context="退款政策 v3：退款期限为签收后的 15 天内。",
    )

    assert draft.answer
    assert draft.conditions
    assert draft.citation_indices == [1]
    assert draft.confidence == 0.85
    assert draft.limitations == []


def test_mock_llm_returns_safe_structured_answer_without_evidence() -> None:
    """没有证据时，应返回保守回答，并且不包含引用。"""

    provider = MockLLMProvider()

    draft = provider.generate_answer(
        question="退款期限是多少？",
        context="",
    )

    assert draft.answer == (
        "当前知识库中没有足够的有效证据，"
        "暂时无法可靠回答这个问题。"
    )
    assert draft.conditions == []
    assert draft.citation_indices == []
    assert draft.confidence == 0.0
    assert draft.limitations


def test_validate_active_current_citation() -> None:
    """当前有效、已生效且未过期的引用应当通过校验。"""

    result = make_retrieval_result()

    assert validate_answer_citations(
        "根据当前政策，退款期限为 15 天。[1]",
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
    """无效状态、未生效、已过期或空内容的证据都应被拒绝。"""

    assert not validate_answer_citations(
        "根据当前政策，退款期限为 15 天。[1]",
        [result],
        [1],
    )


def test_reject_out_of_range_citation() -> None:
    """超出检索结果范围的引用编号应被拒绝。"""

    result = make_retrieval_result()

    assert not validate_answer_citations(
        "根据当前政策，退款期限为 15 天。[2]",
        [result],
        [2],
    )


def test_reject_mismatched_text_and_structured_citations() -> None:
    """文本中的引用编号和结构化引用编号不一致时应被拒绝。"""

    result = make_retrieval_result()

    assert not validate_answer_citations(
        "根据当前政策，退款期限为 15 天。[1]",
        [result],
        [2],
    )


def test_build_citation_from_structured_index() -> None:
    """有效的结构化引用编号应映射到真实检索结果。"""

    result = make_retrieval_result()

    citations = build_citations_from_answer(
        "根据当前政策，退款期限为 15 天。[1]",
        [result],
        [1],
    )

    assert len(citations) == 1
    assert citations[0].document_id == result.document_id
    assert citations[0].document_version_id == result.document_version_id
    assert citations[0].chunk_id == result.chunk_id
    assert citations[0].quote == result.content
    assert citations[0].relevance_score == result.similarity