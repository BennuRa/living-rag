from uuid import UUID

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.document import (
    Document,
    DocumentStatus,
    DocumentVersion,
    DocumentVersionStatus,
)
from app.models.document_chunk import DocumentChunk


def test_create_document_and_first_version(db_session: Session) -> None:
    """A document and its first content snapshot keep their relationship and defaults."""

    document = Document(
        title="会员退款政策",
        metadata_={
            "source": "admin_upload",
            "language": "zh-CN",
        },
    )

    version = DocumentVersion(
        document=document,
        version_number=1,
        content="会员退款申请需在购买后 7 天内提交。",
        content_hash="a" * 64,
        metadata_={
            "source_file_name": "refund-policy-v1.md",
        },
    )

    db_session.add(document)
    db_session.flush()

    assert isinstance(document.id, UUID)
    assert isinstance(version.id, UUID)
    assert version.document is document
    assert version in document.versions
    assert document.status is DocumentStatus.ACTIVE
    assert version.status is DocumentVersionStatus.PENDING
    assert document.metadata_ == {
        "source": "admin_upload",
        "language": "zh-CN",
    }
    assert version.metadata_ == {
        "source_file_name": "refund-policy-v1.md",
    }


def test_reject_duplicate_version_number_for_the_same_document(
    db_session: Session,
) -> None:
    """One document cannot have two versions with the same version number."""

    document = Document(title="会员退款政策")

    first_version = DocumentVersion(
        document=document,
        version_number=1,
        content="第一版退款政策。",
        content_hash="b" * 64,
    )

    db_session.add(document)
    db_session.flush()

    assert first_version.document_id == document.id

    duplicate_version = DocumentVersion(
        document=document,
        version_number=1,
        content="错误地再次创建的第一版退款政策。",
        content_hash="c" * 64,
    )

    db_session.add(duplicate_version)

    with pytest.raises(IntegrityError):
        db_session.flush()

    db_session.rollback()


@pytest.mark.parametrize("invalid_version_number", [0, -1])
def test_reject_non_positive_version_number(
    db_session: Session,
    invalid_version_number: int,
) -> None:
    """A document version number must be greater than zero."""

    document = Document(title="会员退款政策")

    db_session.add(document)
    db_session.flush()

    invalid_version = DocumentVersion(
        document=document,
        version_number=invalid_version_number,
        content="非法版本号测试内容。",
        content_hash="d" * 64,
    )

    db_session.add(invalid_version)

    with pytest.raises(IntegrityError):
        db_session.flush()

    db_session.rollback()


def test_create_ordered_chunks_for_a_document_version(
    db_session: Session,
) -> None:
    """A document version can own ordered, traceable text chunks."""

    document = Document(title="会员退款政策")

    version = DocumentVersion(
        document=document,
        version_number=1,
        content="会员退款政策完整正文。",
        content_hash="e" * 64,
    )

    chunk_zero = DocumentChunk(
        document_version=version,
        chunk_index=0,
        content="普通会员签收后 15 天内可以申请退款。",
        content_hash="f" * 64,
        char_start=0,
        char_end=21,
        metadata_={
            "heading": "退款时限",
        },
    )

    chunk_one = DocumentChunk(
        document_version=version,
        chunk_index=1,
        content="金卡会员指定商品可以享受免运费退货。",
        content_hash="1" * 64,
        char_start=21,
        char_end=40,
        metadata_={
            "heading": "会员权益",
        },
    )

    db_session.add(document)
    db_session.flush()

    assert chunk_zero.document_version is version
    assert chunk_one.document_version is version
    assert version.chunks == [chunk_zero, chunk_one]
    assert [chunk.chunk_index for chunk in version.chunks] == [0, 1]
    assert chunk_zero.content_hash == "f" * 64
    assert chunk_one.content_hash == "1" * 64
    assert chunk_zero.metadata_ == {
        "heading": "退款时限",
    }
    assert chunk_one.metadata_ == {
        "heading": "会员权益",
    }


def test_reject_duplicate_chunk_index_for_the_same_document_version(
    db_session: Session,
) -> None:
    """One document version cannot have two chunks with the same index."""

    document = Document(title="会员退款政策")

    version = DocumentVersion(
        document=document,
        version_number=1,
        content="会员退款政策完整正文。",
        content_hash="g" * 64,
    )

    first_chunk = DocumentChunk(
        document_version=version,
        chunk_index=0,
        content="第一段退款政策内容。",
        content_hash="h" * 64,
    )

    db_session.add(document)
    db_session.flush()

    assert first_chunk.document_version is version

    duplicate_chunk = DocumentChunk(
        document_version=version,
        chunk_index=0,
        content="错误地再次使用相同索引的内容。",
        content_hash="i" * 64,
    )

    db_session.add(duplicate_chunk)

    with pytest.raises(IntegrityError):
        db_session.flush()

    db_session.rollback()


@pytest.mark.parametrize("invalid_chunk_index", [-1, -10])
def test_reject_negative_chunk_index(
    db_session: Session,
    invalid_chunk_index: int,
) -> None:
    """A document chunk index must be zero or greater."""

    document = Document(title="会员退款政策")

    version = DocumentVersion(
        document=document,
        version_number=1,
        content="会员退款政策完整正文。",
        content_hash="j" * 64,
    )

    db_session.add(document)
    db_session.flush()

    invalid_chunk = DocumentChunk(
        document_version=version,
        chunk_index=invalid_chunk_index,
        content="非法索引测试内容。",
        content_hash="k" * 64,
    )

    db_session.add(invalid_chunk)

    with pytest.raises(IntegrityError):
        db_session.flush()

    db_session.rollback()


@pytest.mark.parametrize(
    "blank_content",
    [
        "",
        "   ",
        "\t\n",
    ],
)
def test_reject_blank_chunk_content(
    db_session: Session,
    blank_content: str,
) -> None:
    """A document chunk must contain non-blank text."""

    document = Document(title="会员退款政策")

    version = DocumentVersion(
        document=document,
        version_number=1,
        content="会员退款政策完整正文。",
        content_hash="l" * 64,
    )

    db_session.add(document)
    db_session.flush()

    invalid_chunk = DocumentChunk(
        document_version=version,
        chunk_index=0,
        content=blank_content,
        content_hash="m" * 64,
    )

    db_session.add(invalid_chunk)

    with pytest.raises(IntegrityError):
        db_session.flush()

    db_session.rollback()