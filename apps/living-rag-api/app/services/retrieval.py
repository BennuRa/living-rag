"""Database retrieval service using pgvector similarity search."""

from datetime import UTC, datetime

from sqlalchemy import case, literal, or_, select
from sqlalchemy.orm import Session

from app.models.document import (
    Document,
    DocumentGovernanceStatus,
    DocumentSourceType,
    DocumentVersion,
    DocumentVersionStatus,
)
from app.models.document_chunk import DocumentChunk


def _preferred_policy_keys(query_text: str) -> tuple[str, ...]:
    """根据用户问题识别当前检索的优先政策领域。"""
    normalized_query = query_text.strip().lower()

    refund_keywords = (
        "退款",
        "退货",
        "退费",
        "退款时限",
        "退款期限",
        "退款政策",
        "申请退款",
        "签收后多久",
        "免费退货",
        "运费",
        "refund",
        "return",
        "refund policy",
    )

    delivery_keywords = (
        "配送",
        "物流",
        "发货",
        "运输",
        "延迟",
        "送达",
        "delivery",
        "shipping",
        "物流政策",
    )

    membership_keywords = (
        "会员",
        "会员权益",
        "会员等级",
        "普通会员",
        "银卡",
        "金卡",
        "铂金",
        "membership",
        "membership benefit",
    )

    if any(keyword in normalized_query for keyword in refund_keywords):
        return (
            "REFUND-POLICY",
            "REFUND-FAQ-001",
            "DOUBLE-11-REFUND-NOTICE-2025",
        )

    if any(keyword in normalized_query for keyword in delivery_keywords):
        return (
            "DELIVERY-POLICY",
        )

    if any(keyword in normalized_query for keyword in membership_keywords):
        return (
            "MEMBERSHIP-BENEFITS",
        )

    return ()


def search_similar_chunks(
    db: Session,
    query_embedding: list[float],
    *,
    query_text: str = "",
    limit: int = 5,
    now: datetime | None = None,
) -> list[tuple[DocumentChunk, DocumentVersion, Document, float]]:
    """查询当前有效版本中最相似的文档 Chunk。

    检索排序顺序：

    1. 与问题所属政策领域匹配的文档；
    2. 正式政策；
    3. 临时公告；
    4. FAQ；
    5. 运营通知及其他来源；
    6. 向量余弦距离。

    这样可以避免“会员权益正式政策”因为 source_type 更权威，
    反而压过“退款政策正式政策”的问题。

    Args:
        db: 当前数据库会话。
        query_embedding: 用户问题对应的查询向量。
        query_text: 用户原始问题，用于识别优先政策领域。
        limit: 最多返回的 Chunk 数量。
        now: 用于判断版本有效期的时间。未传入时使用当前 UTC 时间。

    Returns:
        按政策领域、来源优先级和余弦距离排列的检索结果。
        每条结果依次包含 DocumentChunk、DocumentVersion、Document
        和余弦距离。

    Raises:
        ValueError: 当 limit 不是正整数时抛出。
    """
    if limit <= 0:
        raise ValueError("limit must be greater than zero.")

    if now is None:
        now = datetime.now(UTC)

    preferred_policy_keys = _preferred_policy_keys(query_text)

    distance = DocumentChunk.embedding.cosine_distance(
        query_embedding,
    ).label("distance")

    if preferred_policy_keys:
        policy_priority = case(
            (
                Document.policy_key.in_(preferred_policy_keys),
                0,
            ),
            else_=1,
        ).label("policy_priority")
    else:
        policy_priority = literal(0).label("policy_priority")

    source_priority = case(
        (
            DocumentVersion.source_type
            == DocumentSourceType.OFFICIAL_POLICY,
            0,
        ),
        (
            DocumentVersion.source_type
            == DocumentSourceType.TEMPORARY_NOTICE,
            1,
        ),
        (
            DocumentVersion.source_type
            == DocumentSourceType.FAQ,
            2,
        ),
        (
            DocumentVersion.source_type
            == DocumentSourceType.OPERATION_NOTICE,
            3,
        ),
        else_=3,
    ).label("source_priority")

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
            policy_priority.asc(),
            source_priority.asc(),
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