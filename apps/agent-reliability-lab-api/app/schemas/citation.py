from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class Citation(BaseModel):
    """A normalized evidence citation returned by a target agent."""

    model_config = ConfigDict(extra="forbid")

    document_id: UUID
    document_version_id: UUID
    chunk_id: UUID

    document_title: str | None = None
    version_number: int | None = Field(default=None, gt=0)
    source_type: str | None = None
    governance_status: str | None = None
    effective_at: datetime | None = None
    expires_at: datetime | None = None

    quote: str = Field(min_length=1)
    relevance_score: float | None = Field(default=None, ge=0.0, le=1.0)