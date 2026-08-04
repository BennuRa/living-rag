from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.policy_conflict import PolicyConflictStatus
from app.models.review_task import (
    ReviewDecision,
    ReviewTaskStatus,
    ReviewTaskType,
)
from app.schemas.policy_comparison import (
    PolicyComparisonSeverity,
    PolicyRuleComparisonKind,
)
from app.schemas.policy_rule import PolicyRuleKey


class ReviewRuleResponse(BaseModel):
    """Structured rule details shown in the review workspace."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    rule_key: PolicyRuleKey
    value: object
    conditions: dict[str, object]
    source_quote: str
    effective_at: datetime | None
    expires_at: datetime | None
    confidence: float

    
class ConflictEvidenceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    rule_id: UUID | None
    document_version_id: UUID
    quote: str
    position: int


class ReviewConflictResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    kind: PolicyRuleComparisonKind
    severity: PolicyComparisonSeverity
    rule_key: PolicyRuleKey

    left_rule_id: UUID | None
    right_rule_id: UUID | None

    left_rule: ReviewRuleResponse | None
    right_rule: ReviewRuleResponse | None

    left_document_version_id: UUID
    right_document_version_id: UUID

    reason: str
    recommended_action: str
    status: PolicyConflictStatus
    evidences: list[ConflictEvidenceResponse]


class ReviewTaskResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    conflict_id: UUID
    task_type: ReviewTaskType
    status: ReviewTaskStatus
    assigned_to: UUID | None
    decision: ReviewDecision | None
    decision_reason: str | None
    created_at: datetime
    updated_at: datetime
    resolved_at: datetime | None
    conflict: ReviewConflictResponse


class ReviewTaskDecisionRequest(BaseModel):
    """Request body used to resolve one review task."""

    model_config = ConfigDict(extra="forbid")

    decision: ReviewDecision
    decision_reason: str = Field(min_length=1)