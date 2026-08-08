"""API routes for complete Agent run details."""

from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.run_detail import RunDetailResponse
from app.services.run_detail_service import (
    RunNotFoundError,
    get_run_detail,
)

router = APIRouter(
    prefix="/runs",
    tags=["runs"],
)


@router.get(
    "/{trace_id}",
    response_model=RunDetailResponse,
    status_code=status.HTTP_200_OK,
)
def get_run_detail_route(
    trace_id: UUID,
    db: Session = Depends(get_db),
) -> RunDetailResponse:
    """Return the complete Agent run details for one trace_id."""

    try:
        detail = get_run_detail(
            db=db,
            trace_id=trace_id,
        )

    except RunNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    return RunDetailResponse.model_validate(detail)
