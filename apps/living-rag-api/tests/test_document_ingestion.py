from datetime import datetime

import pytest
from sqlalchemy import func, select

from app.models.document import (
    Document,
    DocumentGovernanceStatus,
    DocumentSourceType,
    DocumentVersion,
)
from app.models.document_chunk import DocumentChunk
from app.services.document_ingestion import (
    DocumentIngestionService,
    VersionChangeType,
    compute_content_hash,
    split_into_chunks,
    split_into_paragraphs,
)

TEST_SOURCE_TYPE = DocumentSourceType.OFFICIAL_POLICY
TEST_EFFECTIVE_AT = datetime.fromisoformat("2026-07-21T00:00:00+08:00")
TEST_EXPIRES_AT = None
TEST_ORIGINAL_FILENAME = "refund_policy_v1.md"
TEST_CONTENT_TYPE = "text/markdown"


def test_compute_content_hash_is_stable() -> None:
    content = "会员退款政策"

    first_hash = compute_content_hash(content)
    second_hash = compute_content_hash(content)

    assert first_hash == second_hash
    assert len(first_hash) == 64


def test_compute_content_hash_changes_when_content_changes() -> None:
    original_hash = compute_content_hash("会员退款政策")
    changed_hash = compute_content_hash("会员退款政策。")

    assert original_hash != changed_hash


def test_find_duplicate_version_returns_matching_version(db_session) -> None:
    document = Document(
        title="会员退款政策",
        policy_key="REFUND-POLICY",
        domain="refund",
    )
    content = "会员退款政策正文。"
    content_hash = compute_content_hash(content)

    version = DocumentVersion(
        document=document,
        version_number=1,
        content=content,
        content_hash=content_hash,
    )

    db_session.add(document)
    db_session.add(version)
    db_session.flush()

    service = DocumentIngestionService(db_session)

    duplicate = service.find_duplicate_version(
        document_id=document.id,
        content_hash=content_hash,
    )

    assert duplicate is version


def test_find_duplicate_version_returns_none_for_different_hash(
    db_session,
) -> None:
    document = Document(
        title="会员退款政策",
        policy_key="REFUND-POLICY",
        domain="refund",
    )
    existing_content = "会员退款政策正文。"
    existing_hash = compute_content_hash(existing_content)

    version = DocumentVersion(
        document=document,
        version_number=1,
        content=existing_content,
        content_hash=existing_hash,
    )

    db_session.add(document)
    db_session.add(version)
    db_session.flush()

    service = DocumentIngestionService(db_session)

    duplicate = service.find_duplicate_version(
        document_id=document.id,
        content_hash=compute_content_hash("会员退款政策正文。新增一句话"),
    )

    assert duplicate is None


def test_find_document_by_policy_key_returns_document(db_session) -> None:
    document = Document(
        title="会员退款政策",
        policy_key="REFUND-POLICY",
        domain="refund",
    )

    db_session.add(document)
    db_session.flush()

    service = DocumentIngestionService(db_session)

    found = service.find_document_by_policy_key("REFUND-POLICY")

    assert found is document


def test_find_document_by_policy_key_returns_none_when_missing(
    db_session,
) -> None:
    service = DocumentIngestionService(db_session)

    found = service.find_document_by_policy_key("UNKNOWN-POLICY")

    assert found is None


def test_get_or_create_document_returns_existing_document(
    db_session,
) -> None:
    existing = Document(
        title="会员退款政策",
        policy_key="REFUND-POLICY",
        domain="refund",
    )
    db_session.add(existing)
    db_session.flush()

    service = DocumentIngestionService(db_session)

    result = service.get_or_create_document(
        title="新的标题",
        domain="新的领域",
        policy_key="REFUND-POLICY",
    )

    assert result is existing
    assert result.title == "会员退款政策"


def test_get_or_create_document_creates_new_document(
    db_session,
) -> None:
    service = DocumentIngestionService(db_session)

    result = service.get_or_create_document(
        title="会员退款政策",
        domain="refund",
        policy_key="REFUND-POLICY",
    )

    assert result.id is not None
    assert result.title == "会员退款政策"
    assert result.domain == "refund"
    assert result.policy_key == "REFUND-POLICY"


def test_get_next_version_number_returns_one_for_new_document(
    db_session,
) -> None:
    document = Document(
        title="会员退款政策",
        policy_key="REFUND-POLICY",
        domain="refund",
    )
    db_session.add(document)
    db_session.flush()

    service = DocumentIngestionService(db_session)

    assert service.get_next_version_number(document.id) == 1


def test_get_next_version_number_returns_after_maximum(
    db_session,
) -> None:
    document = Document(
        title="会员退款政策",
        policy_key="REFUND-POLICY",
        domain="refund",
    )
    db_session.add(document)
    db_session.flush()

    db_session.add_all(
        [
            DocumentVersion(
                document=document,
                version_number=1,
                content="第一版正文",
                content_hash=compute_content_hash("第一版正文"),
            ),
            DocumentVersion(
                document=document,
                version_number=3,
                content="第三版正文",
                content_hash=compute_content_hash("第三版正文"),
            ),
        ]
    )
    db_session.flush()

    service = DocumentIngestionService(db_session)

    assert service.get_next_version_number(document.id) == 4


def test_find_latest_version_returns_none_for_new_document(
    db_session,
) -> None:
    document = Document(
        title="会员退款政策",
        policy_key="REFUND-POLICY",
        domain="refund",
    )
    db_session.add(document)
    db_session.flush()

    service = DocumentIngestionService(db_session)

    assert service.find_latest_version(document.id) is None


def test_classify_version_change_returns_new_for_document_without_versions(
    db_session,
) -> None:
    """没有历史版本时，应识别为新增文档版本。"""

    document = Document(
        title="退款政策",
        policy_key="CLASSIFY-NEW-POLICY",
        domain="refund",
    )
    db_session.add(document)
    db_session.flush()

    service = DocumentIngestionService(db_session)

    change_type = service.classify_version_change(
        document_id=document.id,
        requested_version_number=1,
        content_hash=compute_content_hash("第一版退款政策内容"),
    )

    assert change_type is VersionChangeType.NEW


def test_classify_version_change_returns_duplicate_for_same_content(
    db_session,
) -> None:
    """已有相同内容时，应识别为重复版本。"""

    document = Document(
        title="退款政策",
        policy_key="CLASSIFY-DUPLICATE-POLICY",
        domain="refund",
    )
    db_session.add(document)
    db_session.flush()

    existing_content = "第一版退款政策内容"
    existing_hash = compute_content_hash(existing_content)

    version = DocumentVersion(
        document=document,
        version_number=1,
        content=existing_content,
        content_hash=existing_hash,
    )
    db_session.add(version)
    db_session.flush()

    service = DocumentIngestionService(db_session)

    change_type = service.classify_version_change(
        document_id=document.id,
        requested_version_number=2,
        content_hash=existing_hash,
    )

    assert change_type is VersionChangeType.DUPLICATE


def test_classify_version_change_returns_update_for_next_version(
    db_session,
) -> None:
    """内容发生变化且版本号连续时，应识别为正常更新。"""

    document = Document(
        title="退款政策",
        policy_key="CLASSIFY-UPDATE-POLICY",
        domain="refund",
    )
    db_session.add(document)
    db_session.flush()

    first_content = "第一版退款政策内容"
    first_hash = compute_content_hash(first_content)

    first_version = DocumentVersion(
        document=document,
        version_number=1,
        content=first_content,
        content_hash=first_hash,
    )
    db_session.add(first_version)
    db_session.flush()

    service = DocumentIngestionService(db_session)

    second_content = "第二版退款政策内容，退款期限已经更新"
    second_hash = compute_content_hash(second_content)

    change_type = service.classify_version_change(
        document_id=document.id,
        requested_version_number=2,
        content_hash=second_hash,
    )

    assert change_type is VersionChangeType.UPDATE


def test_classify_version_change_returns_conflict_for_non_sequential_version(
    db_session,
) -> None:
    """版本号不连续时，应识别为疑似冲突。"""

    document = Document(
        title="退款政策",
        policy_key="CLASSIFY-CONFLICT-POLICY",
        domain="refund",
    )
    db_session.add(document)
    db_session.flush()

    first_content = "第一版退款政策内容"
    first_version = DocumentVersion(
        document=document,
        version_number=1,
        content=first_content,
        content_hash=compute_content_hash(first_content),
    )
    db_session.add(first_version)
    db_session.flush()

    service = DocumentIngestionService(db_session)

    second_content = "第三版退款政策内容，跳过了第二版"
    second_hash = compute_content_hash(second_content)

    change_type = service.classify_version_change(
        document_id=document.id,
        requested_version_number=3,
        content_hash=second_hash,
    )

    assert change_type is VersionChangeType.POSSIBLE_CONFLICT
    

def test_find_latest_version_returns_highest_version(
    db_session,
) -> None:
    document = Document(
        title="会员退款政策",
        policy_key="REFUND-POLICY",
        domain="refund",
    )
    db_session.add(document)
    db_session.flush()

    version_one = DocumentVersion(
        document=document,
        version_number=1,
        content="第一版正文",
        content_hash=compute_content_hash("第一版正文"),
    )
    version_three = DocumentVersion(
        document=document,
        version_number=3,
        content="第三版正文",
        content_hash=compute_content_hash("第三版正文"),
    )

    db_session.add_all([version_one, version_three])
    db_session.flush()

    service = DocumentIngestionService(db_session)

    latest = service.find_latest_version(document.id)

    assert latest is version_three
    assert latest.version_number == 3


def test_create_document_version_creates_first_version(
    db_session,
) -> None:
    document = Document(
        title="会员退款政策",
        policy_key="REFUND-POLICY",
        domain="refund",
    )
    db_session.add(document)
    db_session.flush()

    content = "第一版退款政策正文。"
    content_hash = compute_content_hash(content)
    service = DocumentIngestionService(db_session)

    version = service.create_document_version(
        document=document,
        content=content,
        content_hash=content_hash,
        source_type=TEST_SOURCE_TYPE,
        effective_at=TEST_EFFECTIVE_AT,
        expires_at=TEST_EXPIRES_AT,
        original_filename=TEST_ORIGINAL_FILENAME,
        content_type=TEST_CONTENT_TYPE,
    )

    assert version.id is not None
    assert version.version_number == 1
    assert version.content == content
    assert version.content_hash == content_hash
    assert version.source_type is TEST_SOURCE_TYPE
    assert version.effective_at == TEST_EFFECTIVE_AT
    assert version.expires_at is TEST_EXPIRES_AT
    assert version.original_filename == TEST_ORIGINAL_FILENAME
    assert version.content_type == TEST_CONTENT_TYPE
    assert version.supersedes_version_id is None


def test_create_document_version_links_to_previous_version(
    db_session,
) -> None:
    document = Document(
        title="会员退款政策",
        policy_key="REFUND-POLICY",
        domain="refund",
    )
    db_session.add(document)
    db_session.flush()

    service = DocumentIngestionService(db_session)

    first_content = "第一版退款政策正文。"
    first_version = service.create_document_version(
        document=document,
        content=first_content,
        content_hash=compute_content_hash(first_content),
        source_type=TEST_SOURCE_TYPE,
        effective_at=TEST_EFFECTIVE_AT,
        expires_at=TEST_EXPIRES_AT,
        original_filename=TEST_ORIGINAL_FILENAME,
        content_type=TEST_CONTENT_TYPE,
    )

    second_content = "第二版退款政策正文。"
    second_version = service.create_document_version(
        document=document,
        content=second_content,
        content_hash=compute_content_hash(second_content),
        source_type=TEST_SOURCE_TYPE,
        effective_at=TEST_EFFECTIVE_AT,
        expires_at=TEST_EXPIRES_AT,
        original_filename="refund_policy_v2.md",
        content_type=TEST_CONTENT_TYPE,
    )

    assert first_version.source_type is TEST_SOURCE_TYPE
    assert second_version.version_number == 2
    assert second_version.source_type is TEST_SOURCE_TYPE
    assert second_version.effective_at == TEST_EFFECTIVE_AT
    assert second_version.expires_at is TEST_EXPIRES_AT
    assert second_version.original_filename == "refund_policy_v2.md"
    assert second_version.content_type == TEST_CONTENT_TYPE
    assert second_version.supersedes_version_id == first_version.id
    assert first_version.governance_status is DocumentGovernanceStatus.SUPERSEDED
    

def test_split_into_paragraphs_preserves_headings_and_paragraphs() -> None:
    content = (
        "# 退款政策\n\n"
        "## 申请条件\n"
        "用户需要在签收后七天内申请退款。\n\n"
        "## 例外情况\n"
        "特殊商品不适用。"
    )

    chunks = split_into_paragraphs(content)

    assert chunks == [
        "# 退款政策",
        "## 申请条件\n用户需要在签收后七天内申请退款。",
        "## 例外情况\n特殊商品不适用。",
    ]


def test_split_into_chunks_keeps_oversized_first_paragraph_without_empty_chunk() -> None:
    content = "这是一个明显超过限制的长段落。"

    chunks = split_into_chunks(content, max_chars=5)

    assert chunks == [content]
    assert "" not in chunks


def test_split_into_chunks_rejects_non_positive_limit() -> None:
    with pytest.raises(
        ValueError,
        match="max_chars must be greater than zero.",
    ):
        split_into_chunks("退款政策", max_chars=0)


def test_create_document_chunks_assigns_indexes_and_hashes(
    db_session,
) -> None:
    document = Document(
        title="会员退款政策",
        policy_key="REFUND-POLICY",
        domain="refund",
    )
    db_session.add(document)
    db_session.flush()

    content = "完整政策正文。"
    version = DocumentVersion(
        document=document,
        version_number=1,
        content=content,
        content_hash=compute_content_hash(content),
    )
    db_session.add(version)
    db_session.flush()

    service = DocumentIngestionService(db_session)

    chunks = service.create_document_chunks(
        document_version=version,
        chunks=["第一块内容", "第二块内容"],
    )

    assert len(chunks) == 2
    assert chunks[0].chunk_index == 0
    assert chunks[1].chunk_index == 1
    assert chunks[0].content == "第一块内容"
    assert chunks[1].content == "第二块内容"
    assert chunks[0].content_hash == compute_content_hash("第一块内容")
    assert chunks[1].content_hash == compute_content_hash("第二块内容")


def test_create_document_chunks_assigns_indexes_and_hashes(
    db_session,
) -> None:
    document = Document(
        title="会员退款政策",
        policy_key="REFUND-POLICY",
        domain="refund",
    )
    db_session.add(document)
    db_session.flush()

    content = "完整政策正文。"
    version = DocumentVersion(
        document=document,
        version_number=1,
        content=content,
        content_hash=compute_content_hash(content),
    )
    db_session.add(version)
    db_session.flush()

    service = DocumentIngestionService(db_session)

    chunks = service.create_document_chunks(
        document_version=version,
        chunks=["第一块内容", "第二块内容"],
    )

    assert len(chunks) == 2
    assert chunks[0].chunk_index == 0
    assert chunks[1].chunk_index == 1
    assert chunks[0].content == "第一块内容"
    assert chunks[1].content == "第二块内容"
    assert chunks[0].content_hash == compute_content_hash("第一块内容")
    assert chunks[1].content_hash == compute_content_hash("第二块内容")


def test_ingest_content_creates_version_and_chunks(
    db_session,
) -> None:
    document = Document(
        title="会员退款政策",
        policy_key="REFUND-POLICY",
        domain="refund",
    )
    db_session.add(document)
    db_session.flush()

    content = "第一段政策。\n\n第二段政策。"
    service = DocumentIngestionService(db_session)

    version = service.ingest_content(
        document=document,
        content=content,
        requested_version_number=1,
        source_type=TEST_SOURCE_TYPE,
        effective_at=TEST_EFFECTIVE_AT,
        expires_at=TEST_EXPIRES_AT,
        original_filename=TEST_ORIGINAL_FILENAME,
        content_type=TEST_CONTENT_TYPE,
    )

    assert version.version_number == 1
    assert version.content == content
    assert version.content_hash == compute_content_hash(content)
    assert version.source_type is TEST_SOURCE_TYPE
    assert version.effective_at == TEST_EFFECTIVE_AT
    assert version.expires_at is TEST_EXPIRES_AT
    assert version.original_filename == TEST_ORIGINAL_FILENAME
    assert version.content_type == TEST_CONTENT_TYPE

    assert len(version.chunks) == 1
    assert version.chunks[0].chunk_index == 0
    assert version.chunks[0].content == "第一段政策。\n第二段政策。"
    assert version.chunks[0].content_hash == compute_content_hash("第一段政策。\n第二段政策。")


def test_ingest_content_returns_existing_version_for_duplicate_content(
    db_session,
) -> None:
    document = Document(
        title="会员退款政策",
        policy_key="REFUND-POLICY",
        domain="refund",
    )
    db_session.add(document)
    db_session.flush()

    content = "第一段退款政策正文。\n\n第二段退款政策正文。"
    service = DocumentIngestionService(db_session)

    first_version = service.ingest_content(
        document=document,
        content=content,
        requested_version_number=1,
        source_type=TEST_SOURCE_TYPE,
        effective_at=TEST_EFFECTIVE_AT,
        expires_at=TEST_EXPIRES_AT,
        original_filename=TEST_ORIGINAL_FILENAME,
        content_type=TEST_CONTENT_TYPE,
    )

    first_chunk_count = db_session.scalar(
        select(func.count(DocumentChunk.id)).where(
            DocumentChunk.document_version_id == first_version.id,
        )
    )

    second_version = service.ingest_content(
        document=document,
        content=content,
        requested_version_number=1,
        source_type=TEST_SOURCE_TYPE,
        effective_at=TEST_EFFECTIVE_AT,
        expires_at=TEST_EXPIRES_AT,
        original_filename=TEST_ORIGINAL_FILENAME,
        content_type=TEST_CONTENT_TYPE,
    )

    version_count = db_session.scalar(
        select(func.count(DocumentVersion.id)).where(
            DocumentVersion.document_id == document.id,
        )
    )

    second_chunk_count = db_session.scalar(
        select(func.count(DocumentChunk.id)).where(
            DocumentChunk.document_version_id == second_version.id,
        )
    )

    assert first_version.version_number == 1
    assert second_version.id == first_version.id
    assert second_version.version_number == 1

    assert version_count == 1

    assert first_chunk_count is not None
    assert first_chunk_count > 0
    assert second_chunk_count == first_chunk_count


def test_ingest_content_rejects_non_sequential_version_number(
    db_session,
) -> None:
    document = Document(
        title="会员退款政策",
        policy_key="REFUND-POLICY",
        domain="refund",
    )
    db_session.add(document)
    db_session.flush()

    service = DocumentIngestionService(db_session)

    first_content = "第一版退款政策正文。"
    service.ingest_content(
        document=document,
        content=first_content,
        requested_version_number=1,
        source_type=TEST_SOURCE_TYPE,
        effective_at=TEST_EFFECTIVE_AT,
        expires_at=TEST_EXPIRES_AT,
        original_filename=TEST_ORIGINAL_FILENAME,
        content_type=TEST_CONTENT_TYPE,
    )

    second_content = "第二版退款政策正文。"

    with pytest.raises(
        ValueError,
        match="Requested version change is a possible conflict.",
    ):
        service.ingest_content(
            document=document,
            content=second_content,
            requested_version_number=3,
            source_type=TEST_SOURCE_TYPE,
            effective_at=TEST_EFFECTIVE_AT,
            expires_at=TEST_EXPIRES_AT,
            original_filename="refund_policy_v2.md",
            content_type=TEST_CONTENT_TYPE,
        )


def test_list_document_versions_returns_descending_versions(
    db_session,
) -> None:
    document = Document(
        title="会员退款政策",
        policy_key="VERSION-LIST-POLICY",
        domain="refund",
    )
    db_session.add(document)
    db_session.flush()

    service = DocumentIngestionService(db_session)

    first_content = "第一版政策正文。"
    service.create_document_version(
        document=document,
        content=first_content,
        content_hash=compute_content_hash(first_content),
        source_type=TEST_SOURCE_TYPE,
        effective_at=TEST_EFFECTIVE_AT,
        expires_at=TEST_EXPIRES_AT,
        original_filename="refund_policy_v1.md",
        content_type=TEST_CONTENT_TYPE,
    )

    second_content = "第二版政策正文。"
    service.create_document_version(
        document=document,
        content=second_content,
        content_hash=compute_content_hash(second_content),
        source_type=TEST_SOURCE_TYPE,
        effective_at=TEST_EFFECTIVE_AT,
        expires_at=TEST_EXPIRES_AT,
        original_filename="refund_policy_v2.md",
        content_type=TEST_CONTENT_TYPE,
    )

    versions = service.list_document_versions("VERSION-LIST-POLICY")

    assert [version.version_number for version in versions] == [2, 1]


def test_list_document_versions_returns_empty_for_unknown_policy(
    db_session,
) -> None:
    service = DocumentIngestionService(db_session)

    versions = service.list_document_versions("UNKNOWN-POLICY")

    assert versions == []


def test_ingest_content_supersedes_previous_version(
    db_session,
) -> None:
    """通过完整导入流程创建新版本时，旧版本应被标记为已替代。"""

    document = Document(
        title="退款政策",
        policy_key="INGEST-SUPERSEDE-POLICY",
        domain="refund",
    )
    db_session.add(document)
    db_session.flush()

    service = DocumentIngestionService(db_session)

    first_content = "第一版退款政策内容"
    first_version = service.ingest_content(
        document=document,
        content=first_content,
        requested_version_number=1,
        source_type=TEST_SOURCE_TYPE,
        effective_at=TEST_EFFECTIVE_AT,
        expires_at=TEST_EXPIRES_AT,
        original_filename="refund_policy_v1.md",
        content_type=TEST_CONTENT_TYPE,
    )

    second_content = "第二版退款政策内容，退款期限已经更新"
    second_version = service.ingest_content(
        document=document,
        content=second_content,
        requested_version_number=2,
        source_type=TEST_SOURCE_TYPE,
        effective_at=TEST_EFFECTIVE_AT,
        expires_at=TEST_EXPIRES_AT,
        original_filename="refund_policy_v2.md",
        content_type=TEST_CONTENT_TYPE,
    )

    assert first_version.version_number == 1
    assert second_version.version_number == 2
    assert second_version.supersedes_version_id == first_version.id
    assert first_version.governance_status is DocumentGovernanceStatus.SUPERSEDED
    assert second_version.governance_status is DocumentGovernanceStatus.ACTIVE