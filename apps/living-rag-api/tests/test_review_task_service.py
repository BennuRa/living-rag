"""Tests for creating review tasks from policy conflicts."""

from uuid import uuid4

from app.models.document import Document, DocumentVersion
from app.models.policy_conflict import PolicyConflict
from app.models.review_task import (
    ReviewTask,
    ReviewTaskStatus,
)
from app.services.review_task_service import (
    create_review_tasks_for_open_conflicts,
)


def create_document_version(db_session) -> DocumentVersion:
    """Create valid document-version foreign-key targets for a test."""

    document = Document(
        title=f"Review task test document {uuid4()}",
        policy_key=f"REVIEW-TASK-TEST-{uuid4()}",
    )

    db_session.add(document)
    db_session.flush()

    document_version = DocumentVersion(
        document_id=document.id,
        version_number=1,
        content="# Test policy",
        content_hash="a" * 64,
    )

    db_session.add(document_version)
    db_session.flush()

    return document_version


def create_conflict(
    db_session,
    document_version: DocumentVersion,
    *,
    kind: str,
    severity: str = "high",
) -> PolicyConflict:
    """Create one open policy conflict for testing."""

    conflict = PolicyConflict(
        kind=kind,
        severity=severity,
        rule_key="refund.window_days",
        left_rule_id=None,
        right_rule_id=None,
        left_document_version_id=document_version.id,
        right_document_version_id=document_version.id,
        reason="Test policy comparison reason.",
        recommended_action="Create a human review task.",
        status="open",
    )

    db_session.add(conflict)
    db_session.flush()

    return conflict


def test_reviewable_open_conflicts_create_pending_tasks(
    db_session,
) -> None:
    """Conflict, exception, and high-risk cases create tasks."""

    document_version = create_document_version(db_session)

    conflict = create_conflict(
        db_session,
        document_version,
        kind="conflict",
    )

    conditional_exception = create_conflict(
        db_session,
        document_version,
        kind="conditional_exception",
        severity="medium",
    )

    high_risk_error = create_conflict(
        db_session,
        document_version,
        kind="high_risk_error",
    )

    tasks = create_review_tasks_for_open_conflicts(
        db_session,
    )

    assert len(tasks) == 3

    task_conflict_ids = {
        task.conflict_id
        for task in tasks
    }

    assert task_conflict_ids == {
        conflict.id,
        conditional_exception.id,
        high_risk_error.id,
    }

    assert all(
        task.status == ReviewTaskStatus.PENDING.value
        for task in tasks
    )

    assert all(
        task.decision is None
        for task in tasks
    )

    assert all(
        task.decision_reason is None
        for task in tasks
    )


def test_historical_difference_and_update_do_not_create_tasks(
    db_session,
) -> None:
    """Historical differences and ordinary updates need no review task."""

    document_version = create_document_version(db_session)

    create_conflict(
        db_session,
        document_version,
        kind="historical_difference",
        severity="low",
    )

    create_conflict(
        db_session,
        document_version,
        kind="update",
        severity="low",
    )

    tasks = create_review_tasks_for_open_conflicts(
        db_session,
    )

    assert tasks == []


def test_task_creation_is_idempotent(
    db_session,
) -> None:
    """Repeated execution does not create duplicate active tasks."""

    document_version = create_document_version(db_session)

    conflict = create_conflict(
        db_session,
        document_version,
        kind="conflict",
    )

    first_run_tasks = create_review_tasks_for_open_conflicts(
        db_session,
    )

    second_run_tasks = create_review_tasks_for_open_conflicts(
        db_session,
    )

    assert len(first_run_tasks) == 1
    assert second_run_tasks == []
    assert first_run_tasks[0].conflict_id == conflict.id

    stored_tasks = db_session.query(ReviewTask).all()

    assert len(stored_tasks) == 1
    assert stored_tasks[0].conflict_id == conflict.id


def test_cancelled_task_allows_recreating_a_review_task(
    db_session,
) -> None:
    """A cancelled task does not block a new pending task."""

    document_version = create_document_version(db_session)

    conflict = create_conflict(
        db_session,
        document_version,
        kind="high_risk_error",
    )

    cancelled_task = ReviewTask(
        conflict_id=conflict.id,
        task_type="resolve_conflict",
        status=ReviewTaskStatus.CANCELLED.value,
    )

    db_session.add(cancelled_task)
    db_session.flush()

    tasks = create_review_tasks_for_open_conflicts(
        db_session,
    )

    assert len(tasks) == 1
    assert tasks[0].conflict_id == conflict.id
    assert tasks[0].status == ReviewTaskStatus.PENDING.value

    stored_tasks = (
        db_session.query(ReviewTask)
        .filter(
            ReviewTask.conflict_id == conflict.id,
        )
        .all()
    )

    assert len(stored_tasks) == 2