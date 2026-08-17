from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.agent_run_result import AgentRunResult
from app.schemas.agent_task_case import AgentTaskCase
from app.schemas.fault_injection import FaultInjectionConfig
from app.schemas.llm_judge import LLMJudgeReport
from app.schemas.rule_evaluation import RuleEvaluationReport
from app.schemas.run_config import RunConfig


class EvaluationExecutionStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    TIMED_OUT = "timed_out"
    CANCELLED = "cancelled"


class EvaluationDataset(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dataset_id: UUID = Field(default_factory=uuid4)
    name: str = Field(min_length=1, max_length=255)
    source_path: str = Field(min_length=1, max_length=1024)
    version: str = Field(min_length=1, max_length=64)
    imported_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
    )


class EvaluationCase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evaluation_case_id: UUID = Field(default_factory=uuid4)
    dataset_id: UUID
    task: AgentTaskCase
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
    )


class EvaluationRun(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evaluation_run_id: UUID = Field(default_factory=uuid4)
    dataset_id: UUID
    config: RunConfig
    status: EvaluationExecutionStatus = EvaluationExecutionStatus.PENDING

    total_cases: int = Field(default=0, ge=0)
    completed_cases: int = Field(default=0, ge=0)
    succeeded_cases: int = Field(default=0, ge=0)
    failed_cases: int = Field(default=0, ge=0)
    timed_out_cases: int = Field(default=0, ge=0)

    started_at: datetime | None = None
    completed_at: datetime | None = None


class CaseRun(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_run_id: UUID = Field(default_factory=uuid4)
    evaluation_run_id: UUID
    evaluation_case_id: UUID
    status: EvaluationExecutionStatus = EvaluationExecutionStatus.PENDING

    attempt_count: int = Field(default=0, ge=0)
    result: AgentRunResult | None = None
    trace_id: str | None = None
    latency_ms: float | None = Field(default=None, ge=0)
    token_usage: dict[str, int] | None = None
    estimated_cost: float | None = Field(default=None, ge=0)
    error_message: str | None = None

    started_at: datetime | None = None
    completed_at: datetime | None = None


class Evaluation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evaluation_id: UUID = Field(default_factory=uuid4)
    case_run_id: UUID
    evaluator_name: str = Field(min_length=1, max_length=128)
    status: EvaluationExecutionStatus = EvaluationExecutionStatus.PENDING
    score: float | None = Field(default=None, ge=0, le=100)
    passed: bool | None = None
    reason: str | None = None


class FaultInjectionRun(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fault_injection_run_id: UUID = Field(default_factory=uuid4)
    case_run_id: UUID
    fault: FaultInjectionConfig
    status: EvaluationExecutionStatus = EvaluationExecutionStatus.PENDING
    started_at: datetime | None = None
    completed_at: datetime | None = None


class EvaluationRunArtifact(BaseModel):
    """A complete, serializable record of one evaluation run."""

    model_config = ConfigDict(extra="forbid")

    evaluation_run: EvaluationRun
    evaluation_cases: list[EvaluationCase]
    case_runs: list[CaseRun]

    # Day 19 artifacts do not contain this field. The default preserves
    # backward compatibility while allowing Day 21 reports to be persisted.
    rule_evaluations: list[RuleEvaluationReport] = Field(
        default_factory=list,
    )

    # Day 22 Judge results are intentionally independent from deterministic
    # rules. A Judge provider failure is stored as a failed Judge report and
    # never overwrites rule_evaluations or CaseRun outcomes.
    llm_judge_evaluations: list[LLMJudgeReport] = Field(
        default_factory=list,
    )
