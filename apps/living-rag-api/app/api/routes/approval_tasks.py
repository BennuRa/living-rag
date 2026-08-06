"""API routes for business approval tasks."""

from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    Header,
    HTTPException,
    Query,
    status,
)
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.approval_task import (
    ApprovalTask,
    ApprovalTaskStatus,
    ApprovalTaskType,
)
from app.schemas.approval_task import (
    ApprovalTaskDecisionRequest,
    ApprovalTaskResponse,
)
from app.services.approval_task_service import (
    decide_approval_task,
)


router = APIRouter(
    prefix="/approval-tasks",
    tags=["approval-tasks"],
)


@router.get(
    "",
    response_model=list[ApprovalTaskResponse],
)
def list_approval_tasks(
    task_status: ApprovalTaskStatus | None = Query(
        default=None,
        alias="status",
    ),
    task_type: ApprovalTaskType | None = None,
    db: Session = Depends(get_db),
) -> list[ApprovalTaskResponse]:
    """List approval tasks with optional status and type filters."""

    statement = select(ApprovalTask).order_by(
        ApprovalTask.created_at.asc(),
    )

    if task_status is not None:
        statement = statement.where(
            ApprovalTask.status == task_status.value,
        )

    if task_type is not None:
        statement = statement.where(
            ApprovalTask.task_type == task_type.value,
        )

    tasks = db.scalars(statement).all()

    return [
        ApprovalTaskResponse.model_validate(task)
        for task in tasks
    ]


@router.post(
    "/{task_id}/decision",
    response_model=ApprovalTaskResponse,
    status_code=status.HTTP_200_OK,
)
def decide_approval_task_route(
    task_id: UUID,
    payload: ApprovalTaskDecisionRequest,
    decided_by: UUID = Header(
        alias="X-Actor-ID",
    ),
    db: Session = Depends(get_db),
) -> ApprovalTaskResponse:
    """Approve or reject one pending approval task."""

    try:
        decide_approval_task(
            db=db,
            task_id=task_id,
            decision=payload.decision,
            decision_reason=payload.decision_reason,
            decided_by=decided_by,
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

    statement = select(ApprovalTask).where(
        ApprovalTask.id == task_id,
    )

    task = db.scalar(statement)

    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Approval task was not found after decision.",
        )

    return ApprovalTaskResponse.model_validate(task)