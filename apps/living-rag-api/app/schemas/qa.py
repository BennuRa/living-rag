"""Schemas for the Living RAG question-answering API."""

from app.schemas.citation import Citation
from pydantic import BaseModel, ConfigDict, Field


class QuestionAnswerRequest(BaseModel):
    """Request body for the grounded question-answering workflow."""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="forbid",
    )

    question: str = Field(
        min_length=1,
        max_length=2000,
    )
    limit: int = Field(
        default=5,
        ge=1,
        le=20,
    )


class QuestionAnswerResponse(BaseModel):
    """Response body for the grounded question-answering workflow."""

    model_config = ConfigDict(extra="forbid")

    answer: str = Field(min_length=1)
    citation_valid: bool
    citations: list[Citation] = Field(default_factory=list)