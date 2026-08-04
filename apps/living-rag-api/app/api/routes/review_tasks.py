"""API routes for human review tasks."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.database import get_db
from app.models.policy_conflict import PolicyConflict
from app.models.review_task import (
    ReviewTask,
    ReviewTaskStatus,
)
from app.schemas.review_task import (
    ReviewTaskDecisionRequest,
    ReviewTaskResponse,
)
from app.services.review_decision_service import (
    decide_review_task,
)


router = APIRouter(
    prefix="/review-tasks",
    tags=["review-tasks"],
)


@router.get(
    "",
    response_model=list[ReviewTaskResponse],
)
def list_review_tasks(
    status: ReviewTaskStatus | None = None,
    db: Session = Depends(get_db),
) -> list[ReviewTaskResponse]:
    """List review tasks with their conflicts and evidences."""

    statement = (
        select(ReviewTask)
        .options(
            selectinload(ReviewTask.conflict).selectinload(
                PolicyConflict.evidences,
            ),
            selectinload(ReviewTask.conflict).selectinload(
                PolicyConflict.left_rule,
            ),
            selectinload(ReviewTask.conflict).selectinload(
                PolicyConflict.right_rule,
            ),
        )
        .order_by(ReviewTask.created_at)
    )

    if status is not None:
        statement = statement.where(
            ReviewTask.status == status.value,
        )

    tasks = db.scalars(statement).all()

    return [
        ReviewTaskResponse.model_validate(task)
        for task in tasks
    ]


@router.post(
    "/{task_id}/decision",
    response_model=ReviewTaskResponse,
    status_code=status.HTTP_200_OK,
)
def decide_review_task_route(
    task_id: UUID,
    payload: ReviewTaskDecisionRequest,
    db: Session = Depends(get_db),
) -> ReviewTaskResponse:
    """Apply a human decision to one review task."""

    try:
        decide_review_task(
            db=db,
            task_id=task_id,
            decision=payload.decision,
            decision_reason=payload.decision_reason,
        )

        db.commit()

    except ValueError as exc:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    except Exception:
        db.rollback()
        raise

    statement = (
        select(ReviewTask)
        .options(
            selectinload(ReviewTask.conflict).selectinload(
                PolicyConflict.evidences,
            ),
            selectinload(ReviewTask.conflict).selectinload(
                PolicyConflict.left_rule,
            ),
            selectinload(ReviewTask.conflict).selectinload(
                PolicyConflict.right_rule,
            ),
        )
        .where(ReviewTask.id == task_id)
    )

    task = db.scalar(statement)

    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Review task was not found after decision.",
        )

    return ReviewTaskResponse.model_validate(task)
