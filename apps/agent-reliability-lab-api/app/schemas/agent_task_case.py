from __future__ import annotations

from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.fault_injection import FaultInjectionConfig


class AgentTaskCategory(StrEnum):
    NORMAL_POLICY_QA = "normal_policy_qa"
    VERSION_AND_STALE_CONTENT = "version_and_stale_content"
    CONFLICT_CASE = "conflict_case"
    ORDER_MEMBERSHIP_ELIGIBILITY = "order_membership_eligibility"
    HIGH_RISK_ACTION = "high_risk_action"
    MULTI_TURN = "multi_turn"
    FAULT_INJECTION = "fault_injection"
    ADVERSARIAL = "adversarial"


class ExpectedCitation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    policy_key: str | None = None
    version: int | None = Field(default=None, ge=1)
    source_type: str | None = None
    chunk_contains: str | None = None


class AgentTaskCase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: str = Field(
        default_factory=lambda: f"generated-{uuid4()}",
        min_length=1,
        max_length=128,
    )
    name: str = Field(min_length=1, max_length=255)
    category: AgentTaskCategory = AgentTaskCategory.NORMAL_POLICY_QA
    user_input: str = Field(min_length=1)
    context: dict[str, Any] = Field(default_factory=dict)
    expected_route: str = Field(
        default="policy_qa",
        min_length=1,
        max_length=128,
    )
    expected_intent: str | None = None
    expected_citations: list[ExpectedCitation] = Field(default_factory=list)
    expected_behavior: list[str] = Field(min_length=1)
    forbidden_behavior: list[str] = Field(default_factory=list)
    failure_conditions: list[str] = Field(default_factory=list)
    fault_injection: FaultInjectionConfig | None = None
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator(
        "expected_behavior",
        "forbidden_behavior",
        "failure_conditions",
        mode="before",
    )
    @classmethod
    def normalize_text_list(cls, value: Any) -> Any:
        if isinstance(value, str):
            return [value]

        if isinstance(value, list):
            return value

        return value