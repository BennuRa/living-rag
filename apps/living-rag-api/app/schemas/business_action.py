"""Pydantic schemas for business action APIs."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.services.qa_state import Intent
from app.services.risk_gate import RiskAction


class BusinessActionRequest(BaseModel):
    """Request body for one user business action."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    user_id: UUID
    question: str = Field(
        min_length=1,
        max_length=2000,
    )
    as_of: datetime | None = None


class BusinessActionResponse(BaseModel):
    """Response returned after deterministic business routing."""

    model_config = ConfigDict(
        extra="forbid",
    )

    trace_id: UUID
    action: RiskAction
    intent: Intent
    status: str
    message: str
    order_number: str | None = None
    approval_task_id: UUID | None = None
    refund_request_id: UUID | None = None
    order_facts: dict[str, object] | None = None
    membership_facts: dict[str, object] | None = None
    refund_history: dict[str, object] | None = None
    eligibility: dict[str, object] | None = None
