"""Tests for Day 12 conflict-aware QA workflow behavior."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.models.document import (
    Document,
    DocumentGovernanceStatus,
    DocumentSourceType,
    DocumentVersion,
)
from app.models.policy_conflict import (
    PolicyConflict,
    PolicyConflictStatus,
)
from app.models.user import User
from app.core.database import get_db
from app.main import app
from app.models.document_chunk import DocumentChunk
from app.services.embedding import MockEmbeddingProvider
from app.schemas.retrieval import RetrievalResult
from app.services.qa_nodes import (
    check_conflicts_node,
    safe_conflict_response_node,
)


def create_document_version(db_session) -> DocumentVersion:
    """Create a document version that can be referenced by a conflict."""

    document = Document(
        title=f"Day 12 conflict test document {uuid4()}",
        policy_key=f"DAY12-CONFLICT-{uuid4()}",
    )

    db_session.add(document)
    db_session.flush()

    document_version = DocumentVersion(
        document_id=document.id,
        version_number=3,
        status="ready",
        source_type=DocumentSourceType.OFFICIAL_POLICY,
        governance_status=DocumentGovernanceStatus.ACTIVE,
        content="正式退款政策：普通会员签收后 15 天内可以申请退款。",
        content_hash="a" * 64,
    )

    db_session.add(document_version)
    db_session.flush()

    return document_version


def create_retrieval_result(
    document_version: DocumentVersion,
) -> RetrievalResult:
    """Create one active retrieval result for the given document version."""

    now = datetime.now(UTC)

    return RetrievalResult(
        document_id=document_version.document_id,
        document_version_id=document_version.id,
        chunk_id=uuid4(),
        document_title="退款政策",
        version_number=document_version.version_number,
        source_type=DocumentSourceType.OFFICIAL_POLICY,
        governance_status=DocumentGovernanceStatus.ACTIVE,
        effective_at=now,
        expires_at=None,
        content="正式退款政策：普通会员签收后 15 天内可以申请退款。",
        similarity=0.95,
    )


def create_conflict(
    db_session,
    document_version: DocumentVersion,
    *,
    kind: str = "conflict",
    status: str = PolicyConflictStatus.OPEN.value,
) -> PolicyConflict:
    """Create one conflict associated with the retrieved document version."""

    conflict = PolicyConflict(
        kind=kind,
        severity="high",
        rule_key="refund.window_days",
        left_rule_id=None,
        right_rule_id=None,
        left_document_version_id=document_version.id,
        right_document_version_id=document_version.id,
        reason=(
            "正式政策规定退款期限为 15 天，"
            "FAQ 声称所有会员可以在 30 天内退款。"
        ),
        recommended_action="提交人工审核并确认最终适用规则。",
        status=status,
    )

    db_session.add(conflict)
    db_session.flush()

    return conflict


def test_open_conflict_blocks_qa(
    db_session,
) -> None:
    """An open true conflict should route the workflow to safe handling."""

    document_version = create_document_version(db_session)
    retrieval_result = create_retrieval_result(document_version)
    create_conflict(
        db_session,
        document_version,
        kind="conflict",
        status=PolicyConflictStatus.OPEN.value,
    )

    state = {
        "question": "FAQ 说可以 30 天退款，是真的吗？",
        "graded_results": [retrieval_result],
    }

    result = check_conflicts_node(
        state,
        db_session,
    )

    assert result["conflict_blocking"] is True
    assert result["conflict_summaries"]
    assert "refund.window_days" in result["conflict_summaries"][0]
    assert result["conflict_notice"]


def test_high_risk_error_blocks_qa(
    db_session,
) -> None:
    """An open high-risk policy error should block a final conclusion."""

    document_version = create_document_version(db_session)
    retrieval_result = create_retrieval_result(document_version)
    create_conflict(
        db_session,
        document_version,
        kind="high_risk_error",
        status=PolicyConflictStatus.OPEN.value,
    )

    state = {
        "question": "退款是否可以无限期申请？",
        "graded_results": [retrieval_result],
    }

    result = check_conflicts_node(
        state,
        db_session,
    )

    assert result["conflict_blocking"] is True
    assert result["conflict_summaries"]
    assert "high_risk_error" in result["conflict_summaries"][0]


@pytest.mark.parametrize(
    "status",
    [
        PolicyConflictStatus.RESOLVED.value,
        PolicyConflictStatus.DISMISSED.value,
    ],
)
def test_closed_conflict_does_not_block_qa(
    db_session,
    status: str,
) -> None:
    """Resolved or dismissed conflicts must not block current QA."""

    document_version = create_document_version(db_session)
    retrieval_result = create_retrieval_result(document_version)
    create_conflict(
        db_session,
        document_version,
        kind="conflict",
        status=status,
    )

    state = {
        "question": "当前退款期限是多少？",
        "graded_results": [retrieval_result],
    }

    result = check_conflicts_node(
        state,
        db_session,
    )

    assert result["conflict_blocking"] is False
    assert result["conflict_summaries"] == []
    assert result["conflict_notice"] == ""


@pytest.mark.parametrize(
    "kind",
    [
        "historical_difference",
        "update",
        "conditional_exception",
    ],
)
def test_non_blocking_conflict_kinds_do_not_block_qa(
    db_session,
    kind: str,
) -> None:
    """Historical changes, updates, and conditional exceptions do not block QA."""

    document_version = create_document_version(db_session)
    retrieval_result = create_retrieval_result(document_version)
    create_conflict(
        db_session,
        document_version,
        kind=kind,
        status=PolicyConflictStatus.OPEN.value,
    )

    state = {
        "question": "当前退款期限是多少？",
        "graded_results": [retrieval_result],
    }

    result = check_conflicts_node(
        state,
        db_session,
    )

    assert result["conflict_blocking"] is False
    assert result["conflict_summaries"] == []
    assert result["conflict_notice"] == ""


def test_empty_graded_results_do_not_report_conflict(
    db_session,
) -> None:
    """Missing valid evidence must not be confused with a policy conflict."""

    state = {
        "question": "当前退款期限是多少？",
        "graded_results": [],
    }

    result = check_conflicts_node(
        state,
        db_session,
    )

    assert result["conflict_blocking"] is False
    assert result["conflict_summaries"] == []
    assert result["conflict_notice"] == ""


def test_safe_conflict_response_is_conservative(
    db_session,
) -> None:
    """The safe branch should request review and avoid a confident conclusion."""

    document_version = create_document_version(db_session)
    retrieval_result = create_retrieval_result(document_version)
    create_conflict(
        db_session,
        document_version,
        kind="conflict",
        status=PolicyConflictStatus.OPEN.value,
    )

    state = {
        "question": "FAQ 说可以 30 天退款，是真的吗？",
        "graded_results": [retrieval_result],
    }

    conflict_result = check_conflicts_node(
        state,
        db_session,
    )

    safe_state = {
        **state,
        **conflict_result,
    }

    result = safe_conflict_response_node(safe_state)

    assert result["answer"]
    assert "人工审核" in result["answer"]
    assert result["conditions"]
    assert result["confidence"] == 0.0
    assert result["limitations"]
    assert result["citation_indices"] == [1]


def test_safe_conflict_response_has_no_citations_without_evidence() -> None:
    """The safe branch should not invent citations when no evidence exists."""

    state = {
        "question": "FAQ 说可以 30 天退款，是真的吗？",
        "graded_results": [],
        "conflict_summaries": [
            "conflict (high) for refund.window_days: policy conflict",
        ],
        "conflict_blocking": True,
        "conflict_notice": (
            "当前检索到的有效证据之间存在尚未完成人工审核的政策冲突。"
        ),
    }

    result = safe_conflict_response_node(state)

    assert result["answer"]
    assert "人工审核" in result["answer"]
    assert result["citation_indices"] == []
    assert result["confidence"] == 0.0
    assert result["limitations"]


def test_qa_api_returns_structured_safe_conflict_response(
    db_session,
    monkeypatch,
) -> None:
    """The real QA endpoint exposes the safe conflict branch and trace data."""

    from fastapi.testclient import TestClient
    import app.api.routes.qa as qa_route_module

    user = User(
        external_id=f"day12-api-{uuid4()}",
        display_name="Day 12 API test user",
    )
    db_session.add(user)
    db_session.flush()

    official_document = Document(
        title="Official refund policy API test",
        policy_key="REFUND-POLICY",
    )
    faq_document = Document(
        title="Refund FAQ API test",
        policy_key="REFUND-FAQ-001",
    )
    db_session.add_all([official_document, faq_document])
    db_session.flush()

    official_version = DocumentVersion(
        document_id=official_document.id,
        version_number=3,
        status="ready",
        source_type=DocumentSourceType.OFFICIAL_POLICY,
        governance_status=DocumentGovernanceStatus.ACTIVE,
        content="Official policy: refund within 15 days.",
        content_hash="b" * 64,
    )
    faq_version = DocumentVersion(
        document_id=faq_document.id,
        version_number=1,
        status="ready",
        source_type=DocumentSourceType.FAQ,
        governance_status=DocumentGovernanceStatus.ACTIVE,
        content="FAQ: all members may request a refund within 30 days.",
        content_hash="c" * 64,
    )
    db_session.add_all([official_version, faq_version])
    db_session.flush()

    embedding_provider = MockEmbeddingProvider()
    contents = [
        official_version.content,
        faq_version.content,
    ]
    embeddings = embedding_provider.embed_texts(contents)

    db_session.add_all([
        DocumentChunk(
            document_version_id=official_version.id,
            chunk_index=0,
            content=official_version.content,
            content_hash="d" * 64,
            embedding=embeddings[0],
        ),
        DocumentChunk(
            document_version_id=faq_version.id,
            chunk_index=0,
            content=faq_version.content,
            content_hash="e" * 64,
            embedding=embeddings[1],
        ),
    ])

    db_session.add(
        PolicyConflict(
            kind="conflict",
            severity="high",
            rule_key="refund.window_days",
            left_rule_id=None,
            right_rule_id=None,
            left_document_version_id=official_version.id,
            right_document_version_id=faq_version.id,
            reason="Official policy says 15 days; FAQ says 30 days.",
            recommended_action="Require human review.",
            status=PolicyConflictStatus.OPEN.value,
        ),
    )
    db_session.flush()

    # Keep this integration test deterministic and compatible with the mock
    # vectors inserted above, regardless of the developer's .env provider.
    monkeypatch.setattr(
        qa_route_module,
        "create_embedding_provider",
        lambda: embedding_provider,
    )

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/qa/answer",
                json={
                    "user_id": str(user.id),
                    "question": "According to the refund policy, does the FAQ allow 30 days?",
                    "limit": 5,
                },
            )
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 200

    payload = response.json()

    assert payload["conflict_blocking"] is True
    assert payload["conflict_summaries"]
    assert payload["conflict_notice"]
    assert payload["confidence"] == 0.0
    assert payload["citation_valid"] is True
    assert payload["trace_id"]
