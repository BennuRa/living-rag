from __future__ import annotations

from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class RuleCheckStatus(StrEnum):
    PASSED = "passed"
    FAILED = "failed"
    NOT_EVALUATED = "not_evaluated"


class RuleCheckName(StrEnum):
    RUN_SUCCEEDED = "run_succeeded"
    FINAL_ANSWER_PRESENT = "final_answer_present"
    TRACE_ID_PRESENT = "trace_id_present"
    EXPECTED_INTENT = "expected_intent"
    EXPECTED_NODES = "expected_nodes"
    EXPECTED_TOOLS = "expected_tools"
    EXPECTED_CITATIONS = "expected_citations"
    CITATIONS_CURRENTLY_VALID = "citations_currently_valid"
    REQUIRED_ANSWER_TERMS = "required_answer_terms"
    APPROVAL_CREATED = "approval_created"
    HIGH_RISK_ACTION_NOT_DIRECTLY_EXECUTED = "high_risk_action_not_directly_executed"
    EMPTY_RETRIEVAL_SAFE_RESPONSE = "empty_retrieval_safe_response"
    UNRESOLVED_CONFLICT_DEFERRED = "unresolved_conflict_deferred"


class RuleCheck(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: RuleCheckName
    status: RuleCheckStatus
    reason: str = Field(min_length=1)
    evidence: dict[str, Any] = Field(default_factory=dict)
    blocks_release: bool = False


class RuleEvaluationReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_run_id: UUID
    evaluator_name: str = "deterministic_rules"
    checks: list[RuleCheck] = Field(min_length=1)

    score: float = Field(ge=0, le=100)
    passed: bool
    release_blocked: bool
    failure_reasons: list[str] = Field(default_factory=list)

    evaluated_check_count: int = Field(ge=0)
    passed_check_count: int = Field(ge=0)
    failed_check_count: int = Field(ge=0)
    not_evaluated_check_count: int = Field(ge=0)
