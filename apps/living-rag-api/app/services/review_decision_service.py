"""Service for resolving human review tasks."""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.document import (
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


def decide_review_task(
    db: Session,
    task_id: UUID,
    decision: ReviewDecision,
    decision_reason: str,
) -> ReviewTask:
    """Apply one human decision to a review task.

    The function updates the review task and its related conflict.
    When the decision is ``invalidate_document``, the right-side
    document version is also marked as invalid.
    """

    normalized_reason = decision_reason.strip()

    if not normalized_reason:
        raise ValueError(
            "Review decision reason cannot be empty."
        )

    statement = (
        select(ReviewTask)
        .options(
            selectinload(ReviewTask.conflict),
        )
        .where(ReviewTask.id == task_id)
    )

    task = db.scalar(statement)

    if task is None:
        raise ValueError(
            f"Review task not found: {task_id}"
        )

    allowed_statuses = {
        ReviewTaskStatus.PENDING.value,
        ReviewTaskStatus.IN_PROGRESS.value,
    }

    if task.status not in allowed_statuses:
        raise ValueError(
            "Only pending or in-progress review tasks can be decided."
        )

    conflict = task.conflict

    if conflict is None:
        raise ValueError(
            "Review task is missing its related policy conflict."
        )

    if decision == ReviewDecision.APPROVE:
        conflict.status = PolicyConflictStatus.RESOLVED.value

    elif decision == ReviewDecision.REJECT:
        conflict.status = PolicyConflictStatus.DISMISSED.value

    elif decision == ReviewDecision.INVALIDATE_DOCUMENT:
        document_version_statement = select(DocumentVersion).where(
            DocumentVersion.id == conflict.right_document_version_id,
        )

        document_version = db.scalar(
            document_version_statement,
        )

        if document_version is None:
            raise ValueError(
                "Right-side document version was not found."
            )

        document_version.governance_status = (
            DocumentGovernanceStatus.INVALID
        )

        conflict.status = PolicyConflictStatus.RESOLVED.value

    else:
        raise ValueError(
            f"Unsupported review decision: {decision}"
        )

    task.decision = decision.value
    task.decision_reason = normalized_reason
    task.status = ReviewTaskStatus.COMPLETED.value
    task.resolved_at = datetime.now(UTC)

    db.flush()

    return task