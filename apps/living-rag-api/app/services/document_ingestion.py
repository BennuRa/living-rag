import hashlib
import re
from datetime import datetime
from uuid import UUID
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from enum import StrEnum
from app.models.document import (
    Document,
    DocumentGovernanceStatus,
    DocumentSourceType,
    DocumentVersion,
)
from app.models.document_chunk import DocumentChunk

class VersionChangeType(StrEnum):
    NEW = "new"
    DUPLICATE = "duplicate"
    UPDATE = "update"
    POSSIBLE_CONFLICT = "possible_conflict"

def compute_content_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def split_into_paragraphs(content: str) -> list[str]:
    paragraphs = re.split(r"\n\s*\n", content)
    cleaned_paragraphs = []

    for paragraph in paragraphs:
        cleaned_paragraph = paragraph.strip()

        if cleaned_paragraph:
            cleaned_paragraphs.append(cleaned_paragraph)

    return cleaned_paragraphs


def split_into_chunks(
    content: str,
    max_chars: int = 1000,
) -> list[str]:
    if max_chars <= 0:
        raise ValueError("max_chars must be greater than zero.")

    paragraphs = split_into_paragraphs(content)
    chunks: list[str] = []
    current_paragraphs: list[str] = []

    for paragraph in paragraphs:
        candidate = "\n".join([*current_paragraphs, paragraph])

        if current_paragraphs and len(candidate) > max_chars:
            chunks.append("\n".join(current_paragraphs))
            current_paragraphs = [paragraph]
        else:
            current_paragraphs.append(paragraph)

    if current_paragraphs:
        chunks.append("\n".join(current_paragraphs))

    return chunks


def list_document_versions(
    self,
    policy_key: str,
) -> list[DocumentVersion]:
    statement = (
        select(DocumentVersion)
        .join(Document, DocumentVersion.document_id == Document.id)
        .where(Document.policy_key == policy_key)
        .order_by(DocumentVersion.version_number.desc())
    )

    return list(self.db.scalars(statement).all())


class DocumentIngestionService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def find_duplicate_version(
        self,
        document_id: UUID,
        content_hash: str,
    ) -> DocumentVersion | None:
        statement = select(DocumentVersion).where(
            DocumentVersion.document_id == document_id,
            DocumentVersion.content_hash == content_hash,
        )
        return self.db.scalar(statement)

    def find_document_by_policy_key(
        self,
        policy_key: str,
    ) -> Document | None:
        statement = select(Document).where(
            Document.policy_key == policy_key,
        )
        return self.db.scalar(statement)

    def get_or_create_document(
        self,
        title: str,
        domain: str,
        policy_key: str,
    ) -> Document:
        existing = self.find_document_by_policy_key(policy_key)
        if existing is not None:
            return existing

        document = Document(
            title=title,
            domain=domain,
            policy_key=policy_key,
        )
        self.db.add(document)
        self.db.flush()
        return document

    def get_next_version_number(self, document_id: UUID) -> int:
        statement = select(func.max(DocumentVersion.version_number)).where(
            DocumentVersion.document_id == document_id,
        )
        max_version = self.db.scalar(statement)

        if max_version is None:
            return 1

        return max_version + 1

    def find_latest_version(
        self,
        document_id: UUID,
    ) -> DocumentVersion | None:
        statement = (
            select(DocumentVersion)
            .where(DocumentVersion.document_id == document_id)
            .order_by(DocumentVersion.version_number.desc())
            .limit(1)
        )

        return self.db.scalar(statement)

    def classify_version_change(
        self,
        document_id: UUID,
        requested_version_number: int,
        content_hash: str,
    ) -> VersionChangeType:
        duplicate = self.find_duplicate_version(
            document_id,
            content_hash,
        )
        if duplicate:
            return VersionChangeType.DUPLICATE
        latest = self.find_latest_version(document_id)
        if latest is None:
            return VersionChangeType.NEW
        if requested_version_number == latest.version_number + 1:
            return VersionChangeType.UPDATE
        return VersionChangeType.POSSIBLE_CONFLICT
    
    def list_document_versions(
        self,
        policy_key: str,
    ) -> list[DocumentVersion]:
        statement = (
            select(DocumentVersion)
            .join(Document, DocumentVersion.document_id == Document.id)
            .where(Document.policy_key == policy_key)
            .order_by(DocumentVersion.version_number.desc())
        )

        return list(self.db.scalars(statement).all())

    def create_document_version(
        self,
        document: Document,
        content: str,
        content_hash: str,
        source_type: DocumentSourceType,
        effective_at: datetime,
        expires_at: datetime | None,
        original_filename: str | None,
        content_type: str | None,
    ) -> DocumentVersion:
        version_number = self.get_next_version_number(document.id)
        latest = self.find_latest_version(document.id)

        supersedes_version_id = None

        if latest is not None:
            latest.governance_status = DocumentGovernanceStatus.SUPERSEDED
            supersedes_version_id = latest.id

        document_version = DocumentVersion(
            document=document,
            version_number=version_number,
            content=content,
            content_hash=content_hash,
            supersedes_version_id=supersedes_version_id,
            source_type=source_type,
            governance_status=DocumentGovernanceStatus.ACTIVE,
            effective_at=effective_at,
            expires_at=expires_at,
            original_filename=original_filename,
            content_type=content_type,
        )
        self.db.add(document_version)
        self.db.flush()
        return document_version

    def create_document_chunks(
        self,
        document_version: DocumentVersion,
        chunks: list[str],
    ) -> list[DocumentChunk]:
        document_chunks = [
            DocumentChunk(
                document_version=document_version,
                chunk_index=chunk_index,
                content=chunk_content,
                content_hash=compute_content_hash(chunk_content),
            )
            for chunk_index, chunk_content in enumerate(chunks)
        ]
        self.db.add_all(document_chunks)
        self.db.flush()
        return document_chunks

    def ingest_content(
        self,
        document: Document,
        content: str,
        requested_version_number: int,
        source_type: DocumentSourceType,
        effective_at: datetime,
        expires_at: datetime | None,
        original_filename: str | None,
        content_type: str | None,
    ) -> DocumentVersion:
        content_hash = compute_content_hash(content)
        change_type = self.classify_version_change(
            document_id=document.id,
            requested_version_number=requested_version_number,
            content_hash=content_hash,
        )

        if change_type is VersionChangeType.POSSIBLE_CONFLICT:
            raise ValueError(
                "Requested version change is a possible conflict."
            )
        
        duplicate = self.find_duplicate_version(
            document.id,
            content_hash,
        )

        if duplicate is not None:
            return duplicate

        self.validate_requested_version_number(
            document.id,
            requested_version_number,
        )

        version = self.create_document_version(
            document=document,
            content=content,
            content_hash=content_hash,
            source_type=source_type,
            effective_at=effective_at,
            expires_at=expires_at,
            original_filename=original_filename,
            content_type=content_type,
        )

        chunks = split_into_chunks(content)

        self.create_document_chunks(
            document_version=version,
            chunks=chunks,
        )

        return version

    def validate_requested_version_number(
        self,
        document_id: UUID,
        requested_version_number: int,
    ) -> None:
        if self.get_next_version_number(document_id) == requested_version_number:
            return

        raise ValueError("Requested version number does not match the next version.")

    
