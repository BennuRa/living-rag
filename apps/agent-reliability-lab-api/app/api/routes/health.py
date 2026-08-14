from datetime import UTC, datetime

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(tags=["system"])


class HealthResponse(BaseModel):
    status: str
    service: str
    timestamp: datetime


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Read service health",
)
async def read_health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        service="agent-reliability-lab-api",
        timestamp=datetime.now(UTC),
    )