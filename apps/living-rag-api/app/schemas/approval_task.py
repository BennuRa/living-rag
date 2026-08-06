"""Pydantic schemas for business approval task APIs."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.approval_task import (
    ApprovalDecision,
    ApprovalTaskStatus,
    ApprovalTaskType,
)


class ApprovalTaskResponse(BaseModel):
    """API response for one business approval task."""

    model_config = ConfigDict(
        from_attributes=True,
        extra="forbid",
        populate_by_name=True,
    )

    id: UUID
    task_type: ApprovalTaskType
    status: ApprovalTaskStatus
    refund_request_id: UUID | None
    resource_type: str
    resource_id: UUID | None
    requested_by: UUID | None
    trace_id: UUID | None
    reason: str
    decision: ApprovalDecision | None
    decision_reason: str | None
    decided_by: UUID | None
    created_at: datetime
    updated_at: datetime
    decided_at: datetime | None
    metadata: dict[str, object] = Field(
        validation_alias="metadata_",
        serialization_alias="metadata",
    )


class ApprovalTaskDecisionRequest(BaseModel):
    """Request body used to approve or reject one task."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    decision: ApprovalDecision
    decision_reason: str = Field(
        min_length=1,
    )