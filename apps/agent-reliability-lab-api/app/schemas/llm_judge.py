from __future__ import annotations

from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class LLMJudgeStatus(StrEnum):
    """The execution state of one LLM Judge evaluation."""

    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SKIPPED = "skipped"


class LLMJudgeDimensionScore(BaseModel):
    """One explainable quality score returned by the Judge."""

    model_config = ConfigDict(extra="forbid")

    score: int = Field(ge=0, le=5)
    reason: str = Field(min_length=1, max_length=2_000)


class LLMJudgeReport(BaseModel):
    """Structured quality evaluation for one completed CaseRun.

    This is deliberately separate from deterministic rule evaluation:
    a Judge failure must never overwrite rule-evaluation results.
    """

    model_config = ConfigDict(extra="forbid")

    case_run_id: UUID
    evaluator_name: str = "llm_judge"
    judge_model: str | None = Field(default=None, max_length=128)

    status: LLMJudgeStatus

    overall_score: float | None = Field(default=None, ge=0, le=100)
    passed: bool | None = None

    conclusion_correctness: LLMJudgeDimensionScore | None = None
    answer_completeness: LLMJudgeDimensionScore | None = None
    citation_support: LLMJudgeDimensionScore | None = None
    conflict_handling: LLMJudgeDimensionScore | None = None
    safety: LLMJudgeDimensionScore | None = None
    evidence_basedness: LLMJudgeDimensionScore | None = None

    reasoning: str | None = Field(default=None, max_length=4_000)
    error_message: str | None = Field(default=None, max_length=2_000)

    @model_validator(mode="after")
    def validate_status_fields(self) -> LLMJudgeReport:
        if self.status == LLMJudgeStatus.SUCCEEDED:
            if self.overall_score is None:
                raise ValueError(
                    "Succeeded LLM Judge report requires overall_score.",
                )

            if self.passed is None:
                raise ValueError(
                    "Succeeded LLM Judge report requires passed.",
                )

            if not self.reasoning or not self.reasoning.strip():
                raise ValueError(
                    "Succeeded LLM Judge report requires reasoning.",
                )

            if self.error_message is not None:
                raise ValueError(
                    "Succeeded LLM Judge report cannot include error_message.",
                )

        if self.status == LLMJudgeStatus.FAILED:
            if not self.error_message or not self.error_message.strip():
                raise ValueError(
                    "Failed LLM Judge report requires error_message.",
                )

            if self.overall_score is not None:
                raise ValueError(
                    "Failed LLM Judge report cannot include overall_score.",
                )

            if self.passed is not None:
                raise ValueError(
                    "Failed LLM Judge report cannot include passed.",
                )

        if self.status == LLMJudgeStatus.SKIPPED:
            if self.overall_score is not None:
                raise ValueError(
                    "Skipped LLM Judge report cannot include overall_score.",
                )

            if self.passed is not None:
                raise ValueError(
                    "Skipped LLM Judge report cannot include passed.",
                )

        return self