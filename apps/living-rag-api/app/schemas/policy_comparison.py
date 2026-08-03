"""Schemas for policy rule comparison results."""

from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.policy_rule import PolicyRuleKey


class PolicyRuleComparisonKind(StrEnum):
    """Business classification for differences between policy rules."""

    UPDATE = "update"
    HISTORICAL_DIFFERENCE = "historical_difference"
    CONDITIONAL_EXCEPTION = "conditional_exception"
    CONFLICT = "conflict"
    HIGH_RISK_ERROR = "high_risk_error"


class PolicyComparisonSeverity(StrEnum):
    """Severity level for a policy rule comparison result."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class PolicyRuleComparison(BaseModel):
    """Validated comparison result for two policy rule versions."""

    model_config = ConfigDict(extra="forbid")

    kind: PolicyRuleComparisonKind
    severity: PolicyComparisonSeverity
    rule_key: PolicyRuleKey

    left_document_version_id: UUID
    right_document_version_id: UUID

    left_rule_id: UUID | None = None
    right_rule_id: UUID | None = None

    reason: str = Field(
        min_length=1,
    )
    recommended_action: str = Field(
        min_length=1,
    )
    evidence: list[str] = Field(
        min_length=1,
    )