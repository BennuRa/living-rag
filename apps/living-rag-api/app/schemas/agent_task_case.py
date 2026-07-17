"""Shared Reliability Lab task case schemas."""

from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


class AgentTaskCase(BaseModel):
    """One deterministic task used to evaluate an Agent."""

    model_config = ConfigDict(extra="forbid")

    case_id: UUID = Field(default_factory=uuid4)
    name: str = Field(min_length=1, max_length=255)
    user_input: str = Field(min_length=1)
    expected_intent: str | None = None
    expected_behavior: str = Field(min_length=1)
    expected_citations: list[UUID] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)