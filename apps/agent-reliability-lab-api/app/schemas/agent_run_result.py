from __future__ import annotations

from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.citation import Citation


class AgentRunResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["succeeded", "failed", "timed_out"]
    final_answer: str | None = None
    citations: list[Citation] = Field(default_factory=list)
    trace_id: str | None = None
    latency_ms: float = Field(ge=0)
    error_message: str | None = None
    raw_response: dict[str, Any] | None = None

    @model_validator(mode="after")
    def validate_status_fields(self) -> Self:
        if self.status == "succeeded":
            if not self.final_answer or not self.final_answer.strip():
                raise ValueError("succeeded result requires a non-empty final_answer")
            if self.error_message is not None:
                raise ValueError("succeeded result cannot include an error_message")
        else:
            if not self.error_message or not self.error_message.strip():
                raise ValueError("failed or timed_out result requires a non-empty error_message")

        return self
