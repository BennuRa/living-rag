"""Tests for policy conflict persistence and review task creation."""

from uuid import uuid4

from app.models.document import Document, DocumentVersion
from app.models.review_task import (
    ReviewTask,
    ReviewTaskStatus,
)
from app.schemas.policy_comparison import (
    PolicyComparisonSeverity,
    PolicyRuleComparison,
    PolicyRuleComparisonKind,
)
from app.services.policy_conflict_service import (
    persist_policy_comparison,
)


def create_document_version(db_session) -> DocumentVersion:
    """Create a valid document version for the conflict test."""

    document = Document(
        title=f"Automatic review task document {uuid4()}",
        policy_key=f"AUTO-REVIEW-{uuid4()}",
    )

    db_session.add(document)
    db_session.flush()

    document_version = DocumentVersion(
        document_id=document.id,
        version_number=1,
        status="ready",
        source_type="official_policy",
        governance_status="active",
        content="# Test policy",
        content_hash="c" * 64,
    )

    db_session.add(document_version)
    db_session.flush()

    return document_version


def test_persisting_reviewable_conflict_creates_review_task(
    db_session,
) -> None:
    """Persisting a reviewable conflict creates a pending task."""

    document_version = create_document_version(db_session)

    comparison = PolicyRuleComparison(
        kind=PolicyRuleComparisonKind.CONFLICT,
        severity=PolicyComparisonSeverity.HIGH,
        rule_key="refund.window_days",
        left_rule_id=None,
        right_rule_id=None,
        left_document_version_id=document_version.id,
        right_document_version_id=document_version.id,
        reason="The two policies provide different refund windows.",
        recommended_action="Create a human review task.",
        evidence=[
            "The official policy allows 15 days.",
            "The FAQ claims 30 days.",
        ],
    )

    conflict = persist_policy_comparison(
        db_session,
        comparison,
    )

    tasks = (
        db_session.query(ReviewTask)
        .filter(
            ReviewTask.conflict_id == conflict.id,
        )
        .all()
    )

    assert len(tasks) == 1
    assert tasks[0].status == ReviewTaskStatus.PENDING.value
    assert tasks[0].decision is None
    assert tasks[0].decision_reason is None


def test_persisting_historical_difference_does_not_create_task(
    db_session,
) -> None:
    """Historical differences do not require human review."""

    document_version = create_document_version(db_session)

    comparison = PolicyRuleComparison(
        kind=PolicyRuleComparisonKind.HISTORICAL_DIFFERENCE,
        severity=PolicyComparisonSeverity.LOW,
        rule_key="refund.window_days",
        left_rule_id=None,
        right_rule_id=None,
        left_document_version_id=document_version.id,
        right_document_version_id=document_version.id,
        reason="The validity periods do not overlap.",
        recommended_action="Keep both historical records.",
        evidence=[
            "The historical rule was valid for an earlier period.",
            "The current rule is valid for a later period.",
        ],
    )

    conflict = persist_policy_comparison(
        db_session,
        comparison,
    )

    tasks = (
        db_session.query(ReviewTask)
        .filter(
            ReviewTask.conflict_id == conflict.id,
        )
        .all()
    )

    assert tasks == []