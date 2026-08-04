"""Service for creating human review tasks from policy conflicts."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.policy_conflict import (
    PolicyConflict,
    PolicyConflictStatus,
)
from app.models.review_task import (
    ReviewTask,
    ReviewTaskStatus,
    ReviewTaskType,
)
from app.schemas.policy_comparison import (
    PolicyRuleComparisonKind,
)


REVIEWABLE_CONFLICT_KINDS = {
    PolicyRuleComparisonKind.CONFLICT.value,
    PolicyRuleComparisonKind.CONDITIONAL_EXCEPTION.value,
    PolicyRuleComparisonKind.HIGH_RISK_ERROR.value,
}


def create_review_tasks_for_open_conflicts(
    db: Session,
) -> list[ReviewTask]:
    """Create one pending review task for each reviewable open conflict.

    Historical differences do not require manual review because their
    validity periods do not overlap. Existing non-cancelled review tasks
    are reused to keep this operation idempotent.
    """

    open_conflicts_statement = select(PolicyConflict).where(
        PolicyConflict.status == PolicyConflictStatus.OPEN.value,
    )

    open_conflicts = db.scalars(
        open_conflicts_statement,
    ).all()

    created_tasks: list[ReviewTask] = []

    for conflict in open_conflicts:
        if conflict.kind not in REVIEWABLE_CONFLICT_KINDS:
            continue

        existing_task_statement = select(ReviewTask).where(
            ReviewTask.conflict_id == conflict.id,
            ReviewTask.status != ReviewTaskStatus.CANCELLED.value,
        )

        existing_task = db.scalar(existing_task_statement)

        if existing_task is not None:
            continue

        review_task = ReviewTask(
            conflict_id=conflict.id,
            task_type=ReviewTaskType.RESOLVE_CONFLICT,
            status=ReviewTaskStatus.PENDING,
        )

        db.add(review_task)
        created_tasks.append(review_task)

    db.flush()

    return created_tasks