from datetime import UTC, datetime

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(tags=["system"])


class HealthResponse(BaseModel):
    status: str
    service: str
    timestamp: datetime


@router.get("/health", response_model=HealthResponse, summary="Read service health")
async def read_health() -> HealthResponse:
    """A dependency-free health probe used by local development and containers."""
    return HealthResponse(
        status="ok", service="living-rag-api", timestamp=datetime.now(UTC)
    )
