"""API route for deterministic business-action routing."""

from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.business_action import (
    BusinessActionRequest,
    BusinessActionResponse,
)
from app.services.business_action_persistence import (
    save_business_action_run,
)
from app.services.business_action_service import (
    execute_business_action,
)


router = APIRouter(
    prefix="/api/business-actions",
    tags=["business-actions"],
)


@router.post(
    "",
    response_model=BusinessActionResponse,
    status_code=status.HTTP_200_OK,
)
def execute_business_action_route(
    request: BusinessActionRequest,
    db: Session = Depends(get_db),
) -> BusinessActionResponse:
    """Route and persist one user business action."""

    trace_id = uuid4()

    try:
        result = execute_business_action(
            db=db,
            question=request.question,
            user_id=request.user_id,
            trace_id=trace_id,
            as_of=request.as_of,
        )

        save_business_action_run(
            db=db,
            user_id=request.user_id,
            trace_id=trace_id,
            question=request.question,
            result=result,
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

    result_with_trace = {
        **result,
        "trace_id": trace_id,
    }

    return BusinessActionResponse.model_validate(
        result_with_trace,
    )
