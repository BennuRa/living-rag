"""Pydantic schemas for audit-log API responses."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.audit_log import (
    AuditActorType,
    AuditResult,
)


class AuditLogResponse(BaseModel):
    """API response for one immutable audit-log record."""

    model_config = ConfigDict(
        from_attributes=True,
        extra="forbid",
        populate_by_name=True,
    )

    id: UUID
    actor_type: AuditActorType
    actor_id: UUID | None
    action: str
    resource_type: str
    resource_id: UUID | None
    result: AuditResult
    reason: str | None
    before_snapshot: dict[str, object] = Field(
        default_factory=dict,
    )
    after_snapshot: dict[str, object] = Field(
        default_factory=dict,
    )
    trace_id: UUID | None
    metadata: dict[str, object] = Field(
        default_factory=dict,
        validation_alias="metadata_",
        serialization_alias="metadata",
    )
    created_at: datetime