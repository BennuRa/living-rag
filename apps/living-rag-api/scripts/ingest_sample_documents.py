"""Ingest Living RAG sample Markdown documents into versioned document tables.

The script is intentionally idempotent:
- a logical document is matched by metadata.document_key;
- a document version is matched by (document_id, version_number);
- a version's content hash must never change silently;
- chunks are created only when a new document version is created.

Run inside the API container:

    python scripts/ingest_sample_documents.py
"""

from __future__ import annotations

import hashlib
import re
import sys
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core.database import SessionLocal
from app.models.document import (
    Document,
    DocumentStatus,
    DocumentVersion,
    DocumentVersionStatus,
)
from app.models.document_chunk import DocumentChunk


DATA_DIRECTORY = Path("/data/sample_documents")
MAX_CHUNK_CHARACTERS = 1200

EXPECTED_SOURCE_FILES = (
    "delivery_policy_v1.md",
    "double_11_refund_notice.md",
    "invalid_unlimited_refund_notice.md",
    "membership_benefits_v1.md",
    "refund_faq_conflicting.md",
    "refund_policy_v1.md",
    "refund_policy_v2.md",
    "refund_policy_v3.md",
)

REQUIRED_METADATA_FIELDS = (
    "文档编号",
    "文档类型",
    "版本",
    "文档状态",
)

METADATA_LINE_PATTERN = re.compile(r"^-\s*([^：:]+)[：:]\s*(.*?)\s*$")
TITLE_PATTERN = re.compile(r"^#\s+(.+?)\s*$")
SECTION_HEADING_PATTERN = re.compile(r"(?m)^##\s+(.+?)\s*$")
VERSION_PATTERN = re.compile(r"^v(?P<number>\d+)$", re.IGNORECASE)
VERSION_SUFFIX_PATTERN = re.compile(r"-V\d+$", re.IGNORECASE)
TITLE_VERSION_SUFFIX_PATTERN = re.compile(r"\s*[（(]\s*V\d+\s*[）)]\s*$", re.IGNORECASE)

SOURCE_DOCUMENT_STATUSES = {
    "active",
    "archived",
    "invalid",
}


class DocumentIngestionError(ValueError):
    """Raised when a Markdown source file violates the ingestion contract."""


@dataclass(frozen=True)
class ChunkInput:
    """A deterministic Chunk produced from one Markdown source document."""

    chunk_index: int
    content: str
    content_hash: str
    char_start: int
    char_end: int
    heading: str


@dataclass(frozen=True)
class SourceDocument:
    """A validated Markdown source file ready to be persisted."""

    source_file: str
    source_document_id: str
    document_key: str
    title: str
    version_number: int
    source_document_status: str
    document_type: str
    effective_at: str | None
    expires_at: str | None
    applies_to: str | None
    owner_team: str | None
    content: str
    content_hash: str
    chunks: tuple[ChunkInput, ...]


@dataclass
class DocumentIngestionStats:
    """Created, updated and unchanged record counters for console output."""

    documents_created: int = 0
    documents_updated: int = 0
    versions_created: int = 0
    versions_unchanged: int = 0
    chunks_created: int = 0
    chunks_unchanged: int = 0


def fail(source: str, message: str) -> DocumentIngestionError:
    """Build a consistent Markdown validation error."""

    return DocumentIngestionError(f"{source}: {message}")


def sha256_text(value: str) -> str:
    """Return the lowercase SHA-256 hash for one UTF-8 text value."""

    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def normalize_optional_value(value: str | None) -> str | None:
    """Convert blank or '无' metadata values to None."""

    if value is None:
        return None

    normalized_value = value.strip()
    if not normalized_value or normalized_value == "无":
        return None

    return normalized_value


def require_metadata(
    metadata: dict[str, str],
    field_name: str,
    source_file: str,
) -> str:
    """Return one required Markdown metadata value."""

    value = normalize_optional_value(metadata.get(field_name))

    if value is None:
        raise fail(source_file, f"missing required metadata field: {field_name!r}")

    return value


def parse_document_title(content: str, source_file: str) -> str:
    """Read the first Markdown H1 title."""

    for line in content.splitlines():
        if not line.strip():
            continue

        title_match = TITLE_PATTERN.match(line)
        if title_match is None:
            raise fail(source_file, "the first non-empty line must be a Markdown H1 title")

        return title_match.group(1).strip()

    raise fail(source_file, "file is empty")


def parse_metadata_block(content: str, source_file: str) -> dict[str, str]:
    """Parse the metadata bullet list located before the first H2 heading."""

    metadata: dict[str, str] = {}
    found_title = False

    for line in content.splitlines():
        if not found_title:
            if line.strip():
                found_title = True
            continue

        if line.startswith("## "):
            break

        metadata_match = METADATA_LINE_PATTERN.match(line)
        if metadata_match is None:
            continue

        field_name = metadata_match.group(1).strip()
        field_value = metadata_match.group(2).strip()

        if field_name in metadata:
            raise fail(source_file, f"duplicate metadata field: {field_name!r}")

        metadata[field_name] = field_value

    for field_name in REQUIRED_METADATA_FIELDS:
        require_metadata(metadata, field_name, source_file)

    return metadata


def parse_version_number(value: str, source_file: str) -> int:
    """Convert a source value such as v3 into the integer 3."""

    version_match = VERSION_PATTERN.fullmatch(value.strip())

    if version_match is None:
        raise fail(
            source_file,
            "metadata field '版本' must use the format v1, v2, v3 and so on",
        )

    version_number = int(version_match.group("number"))

    if version_number <= 0:
        raise fail(source_file, "metadata field '版本' must be greater than zero")

    return version_number


def build_document_key(source_document_id: str) -> str:
    """Map REFUND-POLICY-V3 to the stable logical key REFUND-POLICY."""

    return VERSION_SUFFIX_PATTERN.sub("", source_document_id.strip()).upper()


def normalize_document_title(title: str) -> str:
    """Map a title such as '退款与退货政策（V3）' to its logical document title."""

    normalized_title = TITLE_VERSION_SUFFIX_PATTERN.sub("", title).strip()

    if not normalized_title:
        raise DocumentIngestionError("Document title cannot be blank after normalization")

    return normalized_title


def trim_bounds(content: str, start: int, end: int) -> tuple[int, int]:
    """Trim surrounding whitespace while preserving original character offsets."""

    while start < end and content[start].isspace():
        start += 1

    while end > start and content[end - 1].isspace():
        end -= 1

    return start, end


def split_long_range(
    content: str,
    start: int,
    end: int,
    heading: str,
) -> list[tuple[int, int, str]]:
    """Split one source range into deterministic chunks no longer than the configured limit."""

    chunks: list[tuple[int, int, str]] = []
    cursor = start

    while cursor < end:
        remaining_length = end - cursor
        candidate_end = min(cursor + MAX_CHUNK_CHARACTERS, end)

        if candidate_end < end:
            paragraph_boundary = content.rfind("\n\n", cursor, candidate_end)
            line_boundary = content.rfind("\n", cursor, candidate_end)

            if paragraph_boundary > cursor:
                candidate_end = paragraph_boundary
            elif line_boundary > cursor:
                candidate_end = line_boundary

        chunk_start, chunk_end = trim_bounds(content, cursor, candidate_end)

        if chunk_start < chunk_end:
            chunks.append((chunk_start, chunk_end, heading))

        if candidate_end >= end:
            break

        cursor = candidate_end

        while cursor < end and content[cursor].isspace():
            cursor += 1

    return chunks


def build_chunks(content: str, source_file: str) -> tuple[ChunkInput, ...]:
    """Create heading-aware, deterministic chunks with character offsets."""

    heading_matches = list(SECTION_HEADING_PATTERN.finditer(content))
    source_ranges: list[tuple[int, int, str]] = []

    if heading_matches:
        source_ranges.append((0, heading_matches[0].start(), "文档元信息"))

        for index, heading_match in enumerate(heading_matches):
            next_start = (
                heading_matches[index + 1].start()
                if index + 1 < len(heading_matches)
                else len(content)
            )
            source_ranges.append(
                (
                    heading_match.start(),
                    next_start,
                    heading_match.group(1).strip(),
                )
            )
    else:
        source_ranges.append((0, len(content), "完整文档"))

    chunks: list[ChunkInput] = []

    for source_start, source_end, heading in source_ranges:
        trimmed_start, trimmed_end = trim_bounds(content, source_start, source_end)

        if trimmed_start == trimmed_end:
            continue

        for chunk_start, chunk_end, chunk_heading in split_long_range(
            content,
            trimmed_start,
            trimmed_end,
            heading,
        ):
            chunk_content = content[chunk_start:chunk_end]

            if not chunk_content.strip():
                raise fail(source_file, "Chunk content cannot be blank")

            chunks.append(
                ChunkInput(
                    chunk_index=len(chunks),
                    content=chunk_content,
                    content_hash=sha256_text(chunk_content),
                    char_start=chunk_start,
                    char_end=chunk_end,
                    heading=chunk_heading,
                )
            )

    if not chunks:
        raise fail(source_file, "no non-empty chunks could be created")

    return tuple(chunks)


def load_source_document(source_file: str) -> SourceDocument:
    """Read, parse and validate one expected Markdown source file."""

    source_path = DATA_DIRECTORY / source_file

    if not source_path.is_file():
        raise DocumentIngestionError(f"Required Markdown file was not found: {source_path}")

    content = source_path.read_text(encoding="utf-8-sig")

    if not content.strip():
        raise fail(source_file, "file is empty")

    title = parse_document_title(content, source_file)
    metadata = parse_metadata_block(content, source_file)

    source_document_id = require_metadata(metadata, "文档编号", source_file)
    document_type = require_metadata(metadata, "文档类型", source_file)
    source_document_status = require_metadata(metadata, "文档状态", source_file).lower()

    if source_document_status not in SOURCE_DOCUMENT_STATUSES:
        allowed_statuses = ", ".join(sorted(SOURCE_DOCUMENT_STATUSES))
        raise fail(
            source_file,
            f"unsupported source document status {source_document_status!r}; "
            f"allowed values: {allowed_statuses}",
        )

    return SourceDocument(
        source_file=source_file,
        source_document_id=source_document_id,
        document_key=build_document_key(source_document_id),
        title=normalize_document_title(title),
        version_number=parse_version_number(require_metadata(metadata, "版本", source_file), source_file),
        source_document_status=source_document_status,
        document_type=document_type,
        effective_at=normalize_optional_value(
            metadata.get("生效日期") or metadata.get("发布时间")
        ),
        expires_at=normalize_optional_value(metadata.get("失效日期")),
        applies_to=normalize_optional_value(metadata.get("适用范围")),
        owner_team=normalize_optional_value(metadata.get("维护部门")),
        content=content,
        content_hash=sha256_text(content),
        chunks=build_chunks(content, source_file),
    )


def ensure_unique_source_values(sources: Iterable[SourceDocument]) -> None:
    """Validate source IDs and logical document versions before opening a DB session."""

    source_document_ids: set[str] = set()
    logical_versions: set[tuple[str, int]] = set()

    for source in sources:
        if source.source_document_id in source_document_ids:
            raise fail(
                source.source_file,
                f"duplicate source document ID: {source.source_document_id!r}",
            )

        source_document_ids.add(source.source_document_id)

        logical_version = (source.document_key, source.version_number)
        if logical_version in logical_versions:
            raise fail(
                source.source_file,
                "two source files resolve to the same logical document version: "
                f"{logical_version!r}",
            )

        logical_versions.add(logical_version)


def load_and_validate_documents() -> tuple[SourceDocument, ...]:
    """Load all Day 3 Markdown files and validate their source-level contract."""

    if not DATA_DIRECTORY.is_dir():
        raise DocumentIngestionError(f"Markdown data directory was not found: {DATA_DIRECTORY}")

    discovered_files = tuple(sorted(path.name for path in DATA_DIRECTORY.glob("*.md")))

    if discovered_files != EXPECTED_SOURCE_FILES:
        raise DocumentIngestionError(
            "Unexpected Markdown file set. "
            f"Expected {list(EXPECTED_SOURCE_FILES)!r}, got {list(discovered_files)!r}"
        )

    sources = tuple(load_source_document(source_file) for source_file in EXPECTED_SOURCE_FILES)
    ensure_unique_source_values(sources)

    return sources


def target_document_status(
    sources: Sequence[SourceDocument],
    document_key: str,
) -> DocumentStatus:
    """Return active if any version of one logical document is source-active."""

    source_statuses = {
        source.source_document_status
        for source in sources
        if source.document_key == document_key
    }

    if "active" in source_statuses:
        return DocumentStatus.ACTIVE

    return DocumentStatus.ARCHIVED


def build_document_metadata(
    sources: Sequence[SourceDocument],
    document_key: str,
) -> dict[str, object]:
    """Build stable logical-document metadata from all its source versions."""

    related_sources = sorted(
        (
            source
            for source in sources
            if source.document_key == document_key
        ),
        key=lambda source: source.version_number,
    )

    return {
        "document_key": document_key,
        "source_document_ids": [
            source.source_document_id
            for source in related_sources
        ],
        "source_files": [
            source.source_file
            for source in related_sources
        ],
        "latest_version_number": max(source.version_number for source in related_sources),
    }


def build_version_metadata(source: SourceDocument) -> dict[str, object]:
    """Build version-level metadata that preserves business governance information."""

    return {
        "document_key": source.document_key,
        "source_document_id": source.source_document_id,
        "source_file": source.source_file,
        "document_type": source.document_type,
        "source_document_status": source.source_document_status,
        "effective_at": source.effective_at,
        "expires_at": source.expires_at,
        "applies_to": source.applies_to,
        "owner_team": source.owner_team,
    }


def build_chunk_metadata(
    source: SourceDocument,
    chunk: ChunkInput,
) -> dict[str, object]:
    """Build metadata retained on every searchable Chunk."""

    return {
        "document_key": source.document_key,
        "source_document_id": source.source_document_id,
        "source_file": source.source_file,
        "version_number": source.version_number,
        "document_type": source.document_type,
        "source_document_status": source.source_document_status,
        "chunk_heading": chunk.heading,
    }


def find_document_by_key(session: Session, document_key: str) -> Document | None:
    """Find one stable logical document by its JSONB business key."""

    documents = session.scalars(
        select(Document).where(
            Document.metadata_.op("->>")("document_key") == document_key
        )
    ).all()

    if len(documents) > 1:
        raise DocumentIngestionError(
            f"Database contains multiple documents with document_key={document_key!r}"
        )

    return documents[0] if documents else None


def validate_existing_chunks(
    session: Session,
    document_version: DocumentVersion,
    expected_chunks: Sequence[ChunkInput],
    source_file: str,
) -> int:
    """Verify that a previously ingested immutable version still has expected chunks."""

    existing_chunks = session.scalars(
        select(DocumentChunk)
        .where(DocumentChunk.document_version_id == document_version.id)
        .order_by(DocumentChunk.chunk_index)
    ).all()

    if len(existing_chunks) != len(expected_chunks):
        raise fail(
            source_file,
            "existing immutable version has a different number of chunks; "
            "create a new document version instead of changing this one",
        )

    for existing_chunk, expected_chunk in zip(existing_chunks, expected_chunks, strict=True):
        if (
            existing_chunk.chunk_index != expected_chunk.chunk_index
            or existing_chunk.content_hash != expected_chunk.content_hash
            or existing_chunk.content != expected_chunk.content
            or existing_chunk.char_start != expected_chunk.char_start
            or existing_chunk.char_end != expected_chunk.char_end
        ):
            raise fail(
                source_file,
                "existing immutable version has Chunk content or offsets that differ "
                "from the source file; create a new document version instead",
            )

    return len(existing_chunks)


def upsert_documents(
    session: Session,
    sources: Sequence[SourceDocument],
    stats: DocumentIngestionStats,
) -> dict[str, Document]:
    """Create or synchronize all stable Document entities."""

    documents_by_key: dict[str, Document] = {}

    for document_key in sorted({source.document_key for source in sources}):
        related_sources = [
            source
            for source in sources
            if source.document_key == document_key
        ]
        logical_title = related_sources[0].title
        document = find_document_by_key(session, document_key)

        if document is None:
            document = Document(
                title=logical_title,
                status=target_document_status(sources, document_key),
                metadata_=build_document_metadata(sources, document_key),
            )
            session.add(document)
            stats.documents_created += 1
        else:
            document.title = logical_title
            document.status = target_document_status(sources, document_key)
            document.metadata_ = build_document_metadata(sources, document_key)
            stats.documents_updated += 1

        documents_by_key[document_key] = document

    session.flush()
    return documents_by_key


def ingest_document_versions(
    session: Session,
    sources: Sequence[SourceDocument],
    documents_by_key: dict[str, Document],
    stats: DocumentIngestionStats,
) -> None:
    """Create immutable versions and their chunks, or verify existing versions."""

    for source in sources:
        document = documents_by_key[source.document_key]

        existing_version = session.scalar(
            select(DocumentVersion).where(
                DocumentVersion.document_id == document.id,
                DocumentVersion.version_number == source.version_number,
            )
        )

        if existing_version is not None:
            if existing_version.content_hash != source.content_hash:
                raise fail(
                    source.source_file,
                    "content hash differs from an existing immutable document version "
                    f"(document_key={source.document_key!r}, "
                    f"version_number={source.version_number}); "
                    "create a new version instead of modifying this file",
                )

            validate_existing_chunks(
                session,
                existing_version,
                source.chunks,
                source.source_file,
            )
            stats.versions_unchanged += 1
            stats.chunks_unchanged += len(source.chunks)
            continue

        document_version = DocumentVersion(
            document_id=document.id,
            version_number=source.version_number,
            status=DocumentVersionStatus.READY,
            content=source.content,
            content_hash=source.content_hash,
            metadata_=build_version_metadata(source),
        )
        session.add(document_version)
        session.flush()

        for chunk in source.chunks:
            session.add(
                DocumentChunk(
                    document_version_id=document_version.id,
                    chunk_index=chunk.chunk_index,
                    content=chunk.content,
                    content_hash=chunk.content_hash,
                    char_start=chunk.char_start,
                    char_end=chunk.char_end,
                    metadata_=build_chunk_metadata(source, chunk),
                )
            )

        stats.versions_created += 1
        stats.chunks_created += len(source.chunks)

    session.flush()


def print_stats(stats: DocumentIngestionStats) -> None:
    """Print stable, human-readable ingestion counters."""

    print(
        "documents: "
        f"created={stats.documents_created}, updated={stats.documents_updated}"
    )
    print(
        "document_versions: "
        f"created={stats.versions_created}, unchanged={stats.versions_unchanged}"
    )
    print(
        "document_chunks: "
        f"created={stats.chunks_created}, unchanged={stats.chunks_unchanged}"
    )


def main() -> None:
    """Read Markdown source documents and ingest them in one atomic transaction."""

    print(f"Reading Markdown source documents from: {DATA_DIRECTORY}")
    sources = load_and_validate_documents()
    stats = DocumentIngestionStats()

    try:
        with SessionLocal() as session:
            with session.begin():
                documents_by_key = upsert_documents(session, sources, stats)
                ingest_document_versions(session, sources, documents_by_key, stats)
    except Exception:
        print(
            "Document ingestion failed. The database transaction was rolled back.",
            file=sys.stderr,
        )
        raise

    print("Document ingestion completed successfully.")
    print_stats(stats)


if __name__ == "__main__":
    main()