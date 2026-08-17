from __future__ import annotations

from typing import Annotated

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    model_validator,
)


class RunConfig(BaseModel):
    """Configuration persisted with one evaluation run."""

    model_config = ConfigDict(extra="forbid")

    workflow_version: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1),
    ]

    prompt_version: str | None = None
    model_name: str | None = None

    timeout_seconds: Annotated[
        float,
        Field(gt=0, le=300),
    ] = 30.0

    max_concurrency: Annotated[
        int,
        Field(ge=1, le=20),
    ] = 3

    max_retries: Annotated[
        int,
        Field(ge=0, le=3),
    ] = 1

    cost_budget: Annotated[
        float | None,
        Field(ge=0),
    ] = None

    # Day 22: Judge settings are stored with the evaluation run so an
    # Artifact can explain whether Judge results were enabled and bounded.
    llm_judge_enabled: bool = False
    llm_judge_model_name: str | None = None

    max_llm_judge_calls: Annotated[
        int,
        Field(ge=0, le=100),
    ] = 0

    @model_validator(mode="after")
    def validate_llm_judge_configuration(self) -> RunConfig:
        if self.llm_judge_enabled:
            if self.llm_judge_model_name is None or not self.llm_judge_model_name.strip():
                raise ValueError(
                    "llm_judge_model_name is required when llm_judge_enabled is true.",
                )

            if self.max_llm_judge_calls == 0:
                raise ValueError(
                    "max_llm_judge_calls must be greater than 0 when llm_judge_enabled is true.",
                )

        elif self.max_llm_judge_calls != 0:
            raise ValueError(
                "max_llm_judge_calls must be 0 when llm_judge_enabled is false.",
            )

        return self
