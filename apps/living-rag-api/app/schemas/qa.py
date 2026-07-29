"""Schemas for the Living RAG question-answering API."""
from uuid import UUID
from app.schemas.citation import Citation
from pydantic import BaseModel, ConfigDict, Field


class GroundedAnswerDraft(BaseModel):
    """Structured answer draft produced by the language model."""

    model_config = ConfigDict(extra="forbid")

    answer: str = Field(min_length=1)
    conditions: list[str] = Field(default_factory=list)
    citation_indices: list[int] = Field(default_factory=list)
    confidence: float = Field(
        ge=0.0,
        le=1.0,
    )
    limitations: list[str] = Field(default_factory=list)
    

class QuestionAnswerRequest(BaseModel):
    """Request body for the grounded question-answering workflow."""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="forbid",
    )

    user_id: UUID
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

    trace_id: UUID
    answer: str = Field(min_length=1)
    conditions: list[str] = Field(default_factory=list)
    citation_valid: bool
    citations: list[Citation] = Field(default_factory=list)
    confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
    )
    limitations: list[str] = Field(default_factory=list)