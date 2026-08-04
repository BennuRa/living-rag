"""Tests for human review task decisions."""

from uuid import uuid4

import pytest

from app.models.document import (
    Document,
    DocumentGovernanceStatus,
    DocumentVersion,
)
from app.models.policy_conflict import (
    PolicyConflict,
    PolicyConflictStatus,
)
from app.models.review_task import (
    ReviewDecision,
    ReviewTask,
    ReviewTaskStatus,
)
from app.services.review_decision_service import (
    decide_review_task,
)


def create_document_version(
    db_session,
    *,
    governance_status: DocumentGovernanceStatus = (
        DocumentGovernanceStatus.ACTIVE
    ),
) -> DocumentVersion:
    """Create a valid document version for foreign-key tests."""

    document = Document(
        title=f"Review decision test document {uuid4()}",
        policy_key=f"REVIEW-DECISION-TEST-{uuid4()}",
    )

    db_session.add(document)
    db_session.flush()

    document_version = DocumentVersion(
        document_id=document.id,
        version_number=1,
        status="ready",
        source_type="official_policy",
        governance_status=governance_status,
        content="# Test policy",
        content_hash="b" * 64,
    )

    db_session.add(document_version)
    db_session.flush()

    return document_version


def create_review_task(
    db_session,
    *,
    governance_status: DocumentGovernanceStatus = (
        DocumentGovernanceStatus.ACTIVE
    ),
) -> tuple[ReviewTask, PolicyConflict, DocumentVersion]:
    """Create one review task and its related open conflict."""

    document_version = create_document_version(
        db_session,
        governance_status=governance_status,
    )

    conflict = PolicyConflict(
        kind="conflict",
        severity="high",
        rule_key="refund.window_days",
        left_rule_id=None,
        right_rule_id=None,
        left_document_version_id=document_version.id,
        right_document_version_id=document_version.id,
        reason="The test rules disagree.",
        recommended_action="Create a human review task.",
        status=PolicyConflictStatus.OPEN.value,
    )

    db_session.add(conflict)
    db_session.flush()

    task = ReviewTask(
        conflict_id=conflict.id,
        task_type="resolve_conflict",
        status=ReviewTaskStatus.PENDING.value,
    )

    db_session.add(task)
    db_session.flush()

    return task, conflict, document_version


def test_approve_completes_task_and_resolves_conflict(
    db_session,
) -> None:
    """Approve closes the task and resolves the conflict."""

    task, conflict, _ = create_review_task(
        db_session,
    )

    result = decide_review_task(
        db=db_session,
        task_id=task.id,
        decision=ReviewDecision.APPROVE,
        decision_reason="The rule was confirmed by human review.",
    )

    assert result.id == task.id
    assert result.status == ReviewTaskStatus.COMPLETED.value
    assert result.decision == ReviewDecision.APPROVE.value
    assert (
        result.decision_reason
        == "The rule was confirmed by human review."
    )
    assert result.resolved_at is not None
    assert conflict.status == PolicyConflictStatus.RESOLVED.value


def test_reject_completes_task_and_dismisses_conflict(
    db_session,
) -> None:
    """Reject closes the task and dismisses the conflict."""

    task, conflict, _ = create_review_task(
        db_session,
    )

    result = decide_review_task(
        db=db_session,
        task_id=task.id,
        decision=ReviewDecision.REJECT,
        decision_reason="The exception must not become a general policy.",
    )

    assert result.status == ReviewTaskStatus.COMPLETED.value
    assert result.decision == ReviewDecision.REJECT.value
    assert (
        result.decision_reason
        == "The exception must not become a general policy."
    )
    assert result.resolved_at is not None
    assert conflict.status == PolicyConflictStatus.DISMISSED.value


def test_invalidate_document_marks_right_version_invalid(
    db_session,
) -> None:
    """Invalidation changes the right document governance status."""

    task, conflict, document_version = create_review_task(
        db_session,
    )

    result = decide_review_task(
        db=db_session,
        task_id=task.id,
        decision=ReviewDecision.INVALIDATE_DOCUMENT,
        decision_reason="The document contains an unsafe refund rule.",
    )

    assert result.status == ReviewTaskStatus.COMPLETED.value
    assert result.decision == ReviewDecision.INVALIDATE_DOCUMENT.value
    assert result.resolved_at is not None
    assert conflict.status == PolicyConflictStatus.RESOLVED.value
    assert (
        document_version.governance_status
        == DocumentGovernanceStatus.INVALID
    )


def test_empty_decision_reason_is_rejected(
    db_session,
) -> None:
    """Whitespace-only reasons must not be accepted."""

    task, conflict, document_version = create_review_task(
        db_session,
    )

    with pytest.raises(
        ValueError,
        match="Review decision reason cannot be empty.",
    ):
        decide_review_task(
            db=db_session,
            task_id=task.id,
            decision=ReviewDecision.APPROVE,
            decision_reason="   ",
        )

    assert task.status == ReviewTaskStatus.PENDING.value
    assert task.decision is None
    assert conflict.status == PolicyConflictStatus.OPEN.value
    assert (
        document_version.governance_status
        == DocumentGovernanceStatus.ACTIVE
    )


def test_completed_task_cannot_be_decided_again(
    db_session,
) -> None:
    """A completed review task cannot be modified a second time."""

    task, conflict, document_version = create_review_task(
        db_session,
    )

    decide_review_task(
        db=db_session,
        task_id=task.id,
        decision=ReviewDecision.APPROVE,
        decision_reason="The first decision is final.",
    )

    with pytest.raises(
        ValueError,
        match=(
            "Only pending or in-progress review tasks can be decided."
        ),
    ):
        decide_review_task(
            db=db_session,
            task_id=task.id,
            decision=ReviewDecision.INVALIDATE_DOCUMENT,
            decision_reason="This must be rejected as a duplicate.",
        )

    assert task.status == ReviewTaskStatus.COMPLETED.value
    assert task.decision == ReviewDecision.APPROVE.value
    assert conflict.status == PolicyConflictStatus.RESOLVED.value
    assert (
        document_version.governance_status
        == DocumentGovernanceStatus.ACTIVE
    )


def test_missing_task_is_rejected(
    db_session,
) -> None:
    """An unknown task ID must produce a clear error."""

    with pytest.raises(
        ValueError,
        match="Review task not found:",
    ):
        decide_review_task(
            db=db_session,
            task_id=uuid4(),
            decision=ReviewDecision.APPROVE,
            decision_reason="This task does not exist.",
        )