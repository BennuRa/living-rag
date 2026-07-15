import pytest
from sqlalchemy.exc import IntegrityError
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.document import (
    Document,
    DocumentStatus,
    DocumentVersion,
    DocumentVersionStatus,
)


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

    invalid_version = DocumentVersion(
        document=document,
        version_number=invalid_version_number,
        content="非法版本号测试内容。",
        content_hash="d" * 64,
    )

    db_session.add(document)
    db_session.add(invalid_version)

    with pytest.raises(IntegrityError):
        db_session.flush()

    db_session.rollback()
