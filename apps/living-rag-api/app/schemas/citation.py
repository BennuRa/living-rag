"""Shared citation schemas."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.document import (
    DocumentGovernanceStatus,
    DocumentSourceType,
)


class Citation(BaseModel):
    """Evidence citation attached to an Agent answer."""

    model_config = ConfigDict(extra="forbid")

    document_id: UUID
    document_version_id: UUID
    chunk_id: UUID

    document_title: str | None = None
    version_number: int | None = Field(
        default=None,
        gt=0,
    )
    source_type: DocumentSourceType | None = None
    governance_status: DocumentGovernanceStatus | None = None
    effective_at: datetime | None = None
    expires_at: datetime | None = None

    quote: str = Field(min_length=1)
    relevance_score: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
    )