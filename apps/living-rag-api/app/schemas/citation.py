"""Shared citation schemas."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class Citation(BaseModel):
    """Evidence citation attached to an Agent answer."""

    model_config = ConfigDict(extra="forbid")

    document_id: UUID
    document_version_id: UUID
    chunk_id: UUID
    quote: str = Field(min_length=1)
    relevance_score: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
    )