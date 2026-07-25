"""Schemas for vector retrieval results."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.document import (
    DocumentGovernanceStatus,
    DocumentSourceType,
)


class RetrievalResult(BaseModel):
    """One current and relevant document chunk returned by retrieval."""

    model_config = ConfigDict(extra="forbid")

    document_id: UUID
    document_version_id: UUID
    chunk_id: UUID
    document_title: str = Field(min_length=1)
    version_number: int = Field(gt=0)
    source_type: DocumentSourceType
    governance_status: DocumentGovernanceStatus
    effective_at: datetime | None = None
    expires_at: datetime | None = None
    content: str = Field(min_length=1)
    similarity: float = Field(ge=-1.0, le=1.0)


class RetrievalSearchRequest(BaseModel):
    """Request body for vector retrieval search."""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        extra="forbid",
    )

    query: str = Field(
        min_length=1,
        max_length=2000,
    )
    limit: int = Field(
        default=5,
        ge=1,
        le=20,
    )