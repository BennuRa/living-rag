"""Database retrieval service using pgvector similarity search."""

from datetime import UTC, datetime

from sqlalchemy import case, func, literal, or_, select
from sqlalchemy.orm import Session, aliased

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
        "退钱",
        "退款政策",
        "退款时限",
        "退款期限",
        "申请退款",
        "签收后退款",
        "退货运费",
        "运费谁承担",
        "refund",
        "return",
        "refund policy",
    )

    delivery_keywords = (
        "配送",
        "物流",
        "发货",
        "快递",
        "运输",
        "送达",
        "配送政策",
        "物流延迟",
        "delivery",
        "shipping",
    )

    membership_keywords = (
        "会员",
        "会员权益",
        "会员等级",
        "普通会员",
        "银卡会员",
        "金卡会员",
        "铂金会员",
        "黑金会员",
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
    as_of_date: datetime | None = None,
) -> list[tuple[DocumentChunk, DocumentVersion, Document, float]]:
    """查询当前或指定历史日期下有效的文档 Chunk。

    默认情况下，检索当前有效版本：

    - 文档 Chunk 必须存在 embedding；
    - 文档版本技术状态必须为 READY；
    - 文档治理状态必须为 ACTIVE；
    - effective_at 不得晚于当前时间；
    - expires_at 为空或晚于当前时间。

    当传入 as_of_date 时，执行历史版本查询：

    - 文档版本技术状态必须为 READY；
    - 文档治理状态允许为 ACTIVE 或 SUPERSEDED；
    - effective_at 不得晚于指定日期；
    - expires_at 为空或晚于指定日期；
    - 同一逻辑文档只选择指定日期下版本号最高的有效版本。

    Args:
        db: 当前数据库会话。
        query_embedding: 用户问题对应的查询向量，必须是 768 维。
        query_text: 用户原始问题，用于识别优先政策领域。
        limit: 最多返回的 Chunk 数量。
        now: 当前查询使用的时间。未传入时使用当前 UTC 时间。
        as_of_date: 可选的历史查询日期。传入后会查询该日期有效的历史版本。

    Returns:
        按政策优先级、来源类型和余弦距离排序的检索结果。
        每条结果依次包含：

        - DocumentChunk；
        - DocumentVersion；
        - Document；
        - 余弦距离。

    Raises:
        ValueError: 当 limit 不是正整数时抛出。
    """

    if limit <= 0:
        raise ValueError("limit must be greater than zero.")

    if now is None:
        now = datetime.now(UTC)

    reference_time = (
        as_of_date
        if as_of_date is not None
        else now
    )

    if as_of_date is None:
        governance_status_condition = (
            DocumentVersion.governance_status
            == DocumentGovernanceStatus.ACTIVE
        )
    else:
        governance_status_condition = (
            DocumentVersion.governance_status.in_(
                (
                    DocumentGovernanceStatus.ACTIVE,
                    DocumentGovernanceStatus.SUPERSEDED,
                ),
            )
        )

    historical_version = aliased(DocumentVersion)

    latest_historical_version_number = (
        select(func.max(historical_version.version_number))
        .where(
            historical_version.document_id
            == DocumentVersion.document_id,
        )
        .where(
            historical_version.status
            == DocumentVersionStatus.READY,
        )
        .where(
            historical_version.governance_status.in_(
                (
                    DocumentGovernanceStatus.ACTIVE,
                    DocumentGovernanceStatus.SUPERSEDED,
                ),
            ),
        )
        .where(
            or_(
                historical_version.effective_at.is_(None),
                historical_version.effective_at <= reference_time,
            ),
        )
        .where(
            or_(
                historical_version.expires_at.is_(None),
                historical_version.expires_at > reference_time,
            ),
        )
        .correlate(DocumentVersion)
        .scalar_subquery()
    )

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
            governance_status_condition,
        )
        .where(
            or_(
                DocumentVersion.effective_at.is_(None),
                DocumentVersion.effective_at <= reference_time,
            ),
        )
        .where(
            or_(
                DocumentVersion.expires_at.is_(None),
                DocumentVersion.expires_at > reference_time,
            ),
        )
    )

    if as_of_date is not None:
        statement = statement.where(
            DocumentVersion.version_number
            == latest_historical_version_number,
        )

    statement = (
        statement
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