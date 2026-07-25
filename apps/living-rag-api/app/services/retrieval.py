"""Database retrieval service using pgvector similarity search."""

from datetime import UTC, datetime

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.document import (
    Document,
    DocumentGovernanceStatus,
    DocumentVersion,
    DocumentVersionStatus,
)
from app.models.document_chunk import DocumentChunk


def search_similar_chunks(
    db: Session,
    query_embedding: list[float],
    *,
    limit: int = 5,
    now: datetime | None = None,
) -> list[tuple[DocumentChunk, DocumentVersion, Document, float]]:
    """查询当前有效版本中最相似的文档 Chunk。

    Args:
        db: 当前数据库会话。
        query_embedding: 用户问题对应的查询向量。
        limit: 最多返回的 Chunk 数量。
        now: 用于判断版本有效期的时间。未传入时使用当前 UTC 时间。

    Returns:
        按余弦距离从小到大排列的检索结果。
        每条结果依次包含 DocumentChunk、DocumentVersion、Document
        和余弦距离。

    Raises:
        ValueError: 当 limit 不是正整数时抛出。
    """
    if limit <= 0:
        raise ValueError("limit must be greater than zero.")

    if now is None:
        now = datetime.now(UTC)

    distance = DocumentChunk.embedding.cosine_distance(
        query_embedding,
    ).label("distance")

    statement = (
        select(
            DocumentChunk,
            DocumentVersion,
            Document,
            distance,
        )
        .join(
            DocumentVersion,
            DocumentVersion.id == DocumentChunk.document_version_id,
        )
        .join(
            Document,
            Document.id == DocumentVersion.document_id,
        )
        .where(
            DocumentChunk.embedding.is_not(None),
        )
        .where(
            DocumentVersion.status == DocumentVersionStatus.READY,
        )
        .where(
            DocumentVersion.governance_status
            == DocumentGovernanceStatus.ACTIVE,
        )
        .where(
            or_(
                DocumentVersion.effective_at.is_(None),
                DocumentVersion.effective_at <= now,
            ),
        )
        .where(
            or_(
                DocumentVersion.expires_at.is_(None),
                DocumentVersion.expires_at > now,
            ),
        )
        .order_by(
            distance.asc(),
        )
        .limit(limit)
    )

    rows = db.execute(statement).all()

    return [
        (
            chunk,
            document_version,
            document,
            float(distance_value),
        )
        for chunk, document_version, document, distance_value in rows
    ]