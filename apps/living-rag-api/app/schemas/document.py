from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.document import (
    DocumentGovernanceStatus,
    DocumentSourceType,
)


class DocumentUploadForm(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    title: str = Field(min_length=1, max_length=255)
    domain: str = Field(min_length=1, max_length=64)
    policy_key: str = Field(min_length=1, max_length=128)
    source_type: DocumentSourceType
    version_number: int = Field(gt=0)
    effective_at: datetime
    expires_at: datetime | None = None

    @field_validator("effective_at", "expires_at")
    @classmethod
    def validate_datetimes(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.tzinfo is None:
            raise ValueError("Datetime values must include a timezone offset.")
        return value

    @model_validator(mode="after")
    def validate_expiration(self) -> "DocumentUploadForm":
        if self.expires_at is not None and self.expires_at <= self.effective_at:
            raise ValueError("expires_at must be later than effective_at.")
        return self


class DocumentUploadResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    document_id: UUID
    document_version_id: UUID
    policy_key: str
    version_number: int
    content_hash: str
    source_type: DocumentSourceType
    effective_at: datetime
    expires_at: datetime | None = None
    original_filename: str | None = None
    content_type: str | None = None
    chunk_count: int


class DocumentVersionListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    document_id: UUID
    document_version_id: UUID
    policy_key: str
    version_number: int
    content_hash: str
    source_type: DocumentSourceType
    governance_status: DocumentGovernanceStatus
    effective_at: datetime
    expires_at: datetime | None = None
    original_filename: str | None = None
    content_type: str | None = None
    chunk_count: int
