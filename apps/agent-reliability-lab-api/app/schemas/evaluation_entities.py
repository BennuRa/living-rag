from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.agent_run_result import AgentRunResult
from app.schemas.agent_task_case import AgentTaskCase
from app.schemas.fault_injection import FaultInjectionConfig
from app.schemas.run_config import RunConfig


class EvaluationExecutionStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
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
    started_at: datetime | None = None
    completed_at: datetime | None = None


class CaseRun(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_run_id: UUID = Field(default_factory=uuid4)
    evaluation_run_id: UUID
    evaluation_case_id: UUID
    status: EvaluationExecutionStatus = EvaluationExecutionStatus.PENDING
    result: AgentRunResult | None = None
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