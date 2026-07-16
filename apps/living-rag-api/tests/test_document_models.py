from uuid import UUID
from decimal import Decimal
from app.models.order import Order, OrderStatus
from app.models.refund_request import (
    RefundRequest,
    RefundRequestStatus,
)
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
from app.models.membership_account import (
    MembershipAccount,
    MembershipAccountStatus,
    MembershipTier,
)
from app.models.chat_message import (
    ChatMessage,
    ChatMessageRole,
    ChatMessageStatus,
)
from app.models.chat_thread import (
    ChatSubject,
    ChatThread,
    ChatThreadStatus,
)
from app.models.user import User, UserStatus

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




def test_create_user_with_defaults_and_metadata(
    db_session: Session,
) -> None:
    """A user keeps identity data, defaults, and metadata."""

    user = User(
        external_id="crm-user-10001",
        email="zhangsan@example.com",
        display_name="张三",
        metadata_={
            "source": "crm_import",
            "language": "zh-CN",
        },
    )

    db_session.add(user)
    db_session.flush()

    assert isinstance(user.id, UUID)
    assert user.external_id == "crm-user-10001"
    assert user.email == "zhangsan@example.com"
    assert user.display_name == "张三"
    assert user.status is UserStatus.ACTIVE
    assert user.metadata_ == {
        "source": "crm_import",
        "language": "zh-CN",
    }


def test_create_disabled_user(
    db_session: Session,
) -> None:
    """A user can be explicitly disabled without being deleted."""

    user = User(
        external_id="crm-user-10002",
        display_name="李四",
        status=UserStatus.DISABLED,
    )

    db_session.add(user)
    db_session.flush()

    assert user.status is UserStatus.DISABLED
    assert user.email is None
    assert user.metadata_ == {}


def test_reject_duplicate_user_external_id(
    db_session: Session,
) -> None:
    """Two users cannot share the same external identity."""

    first_user = User(
        external_id="crm-user-10003",
        display_name="王五",
    )

    db_session.add(first_user)
    db_session.flush()

    duplicate_user = User(
        external_id="crm-user-10003",
        display_name="赵六",
    )

    db_session.add(duplicate_user)

    with pytest.raises(IntegrityError):
        db_session.flush()

    db_session.rollback()





def test_create_membership_account_for_a_user(
    db_session: Session,
) -> None:
    """A user can own one membership account with defaults and metadata."""

    user = User(
        external_id="crm-user-20001",
        display_name="会员用户",
    )

    account = MembershipAccount(
        user=user,
        membership_number="MBR-20001",
        metadata_={
            "source": "crm_import",
            "region": "华东",
        },
    )

    db_session.add(user)
    db_session.flush()

    assert isinstance(account.id, UUID)
    assert account.user is user
    assert user.membership_account is account
    assert account.membership_number == "MBR-20001"
    assert account.tier is MembershipTier.STANDARD
    assert account.status is MembershipAccountStatus.ACTIVE
    assert account.points == 0
    assert account.metadata_ == {
        "source": "crm_import",
        "region": "华东",
    }


def test_reject_two_membership_accounts_for_the_same_user(
    db_session: Session,
) -> None:
    """One user cannot own two membership accounts."""

    user = User(
        external_id="crm-user-20002",
        display_name="重复账户用户",
    )

    first_account = MembershipAccount(
        user=user,
        membership_number="MBR-20002",
    )

    db_session.add(user)
    db_session.flush()

    duplicate_account = MembershipAccount(
        user_id=user.id,
        membership_number="MBR-20003",
    )

    db_session.add(duplicate_account)

    with pytest.raises(IntegrityError):
        db_session.flush()

    db_session.rollback()


def test_reject_duplicate_membership_number(
    db_session: Session,
) -> None:
    """Two membership accounts cannot share the same membership number."""

    first_user = User(
        external_id="crm-user-20003",
        display_name="第一位会员",
    )

    first_account = MembershipAccount(
        user=first_user,
        membership_number="MBR-20004",
    )

    db_session.add(first_user)
    db_session.flush()

    second_user = User(
        external_id="crm-user-20004",
        display_name="第二位会员",
    )

    db_session.add(second_user)
    db_session.flush()

    duplicate_account = MembershipAccount(
        user_id=second_user.id,
        membership_number="MBR-20004",
    )

    db_session.add(duplicate_account)

    with pytest.raises(IntegrityError):
        db_session.flush()

    db_session.rollback()

@pytest.mark.parametrize("invalid_points", [-1, -100])
def test_reject_negative_membership_points(
    db_session: Session,
    invalid_points: int,
) -> None:
    """Membership points cannot be negative."""

    user = User(
        external_id=f"crm-user-points-{abs(invalid_points)}",
        display_name="积分测试用户",
    )

    db_session.add(user)
    db_session.flush()

    invalid_account = MembershipAccount(
        user=user,
        membership_number=f"MBR-POINTS-{abs(invalid_points)}",
        points=invalid_points,
    )

    db_session.add(invalid_account)

    with pytest.raises(IntegrityError):
        db_session.flush()

    db_session.rollback()


def test_create_order_and_refund_request(
    db_session: Session,
) -> None:
    """An order can own a traceable refund request."""

    user = User(
        external_id="crm-user-order-30001",
        display_name="订单测试用户",
    )

    membership_account = MembershipAccount(
        user=user,
        membership_number="MBR-30001",
        tier=MembershipTier.GOLD,
    )

    order = Order(
        membership_account=membership_account,
        order_number="ORD-30001",
        status=OrderStatus.COMPLETED,
        total_amount=Decimal("199.90"),
        metadata_={
            "product_name": "会员年卡",
        },
    )

    refund_request = RefundRequest(
        order=order,
        request_number="REF-30001",
        requested_amount=Decimal("99.90"),
        reason="商品与描述不符",
        metadata_={
            "policy_version": "refund-policy-v3",
        },
    )

    db_session.add(user)
    db_session.flush()

    assert isinstance(order.id, UUID)
    assert isinstance(refund_request.id, UUID)
    assert order.membership_account is membership_account
    assert order in membership_account.orders
    assert refund_request.order is order
    assert refund_request in order.refund_requests
    assert order.status is OrderStatus.COMPLETED
    assert refund_request.status is RefundRequestStatus.PENDING
    assert order.total_amount == Decimal("199.90")
    assert refund_request.requested_amount == Decimal("99.90")
    assert refund_request.approved_amount is None
    assert order.currency == "CNY"
    assert order.metadata_ == {
        "product_name": "会员年卡",
    }
    assert refund_request.metadata_ == {
        "policy_version": "refund-policy-v3",
    }


def test_reject_duplicate_order_number(
    db_session: Session,
) -> None:
    """Two orders cannot share the same order number."""

    user = User(
        external_id="crm-user-order-30002",
        display_name="订单编号测试用户",
    )

    membership_account = MembershipAccount(
        user=user,
        membership_number="MBR-30002",
    )

    first_order = Order(
        membership_account=membership_account,
        order_number="ORD-30002",
        total_amount=Decimal("100.00"),
    )

    db_session.add(user)
    db_session.flush()

    duplicate_order = Order(
        membership_account_id=membership_account.id,
        order_number="ORD-30002",
        total_amount=Decimal("80.00"),
    )

    db_session.add(duplicate_order)

    with pytest.raises(IntegrityError):
        db_session.flush()

    db_session.rollback()


@pytest.mark.parametrize(
    "invalid_total_amount",
    [
        Decimal("-0.01"),
        Decimal("-100.00"),
    ],
)
def test_reject_negative_order_total_amount(
    db_session: Session,
    invalid_total_amount: Decimal,
) -> None:
    """An order total amount cannot be negative."""

    user = User(
        external_id=f"crm-user-order-amount-{abs(invalid_total_amount)}",
        display_name="订单金额测试用户",
    )

    membership_account = MembershipAccount(
        user=user,
        membership_number=f"MBR-AMOUNT-{abs(invalid_total_amount)}",
    )

    db_session.add(user)
    db_session.flush()

    invalid_order = Order(
        membership_account_id=membership_account.id,
        order_number=f"ORD-AMOUNT-{abs(invalid_total_amount)}",
        total_amount=invalid_total_amount,
    )

    db_session.add(invalid_order)

    with pytest.raises(IntegrityError):
        db_session.flush()

    db_session.rollback()


def test_reject_duplicate_refund_request_number(
    db_session: Session,
) -> None:
    """Two refund requests cannot share the same request number."""

    user = User(
        external_id="crm-user-refund-30001",
        display_name="退款编号测试用户",
    )

    membership_account = MembershipAccount(
        user=user,
        membership_number="MBR-REFUND-30001",
    )

    order = Order(
        membership_account=membership_account,
        order_number="ORD-REFUND-30001",
        total_amount=Decimal("100.00"),
    )

    first_request = RefundRequest(
        order=order,
        request_number="REF-30002",
        requested_amount=Decimal("30.00"),
        reason="第一次退款申请",
    )

    db_session.add(user)
    db_session.flush()

    duplicate_request = RefundRequest(
        order_id=order.id,
        request_number="REF-30002",
        requested_amount=Decimal("20.00"),
        reason="重复退款申请编号",
    )

    db_session.add(duplicate_request)

    with pytest.raises(IntegrityError):
        db_session.flush()

    db_session.rollback()


@pytest.mark.parametrize(
    "invalid_requested_amount",
    [
        Decimal("0.00"),
        Decimal("-1.00"),
    ],
)
def test_reject_non_positive_requested_refund_amount(
    db_session: Session,
    invalid_requested_amount: Decimal,
) -> None:
    """A refund request amount must be greater than zero."""

    user = User(
        external_id=f"crm-user-refund-amount-{abs(invalid_requested_amount)}",
        display_name="退款金额测试用户",
    )

    membership_account = MembershipAccount(
        user=user,
        membership_number=f"MBR-REFUND-AMOUNT-{abs(invalid_requested_amount)}",
    )

    order = Order(
        membership_account=membership_account,
        order_number=f"ORD-REFUND-AMOUNT-{abs(invalid_requested_amount)}",
        total_amount=Decimal("100.00"),
    )

    db_session.add(user)
    db_session.flush()

    invalid_request = RefundRequest(
        order_id=order.id,
        request_number=f"REF-REFUND-AMOUNT-{abs(invalid_requested_amount)}",
        requested_amount=invalid_requested_amount,
        reason="非法退款金额测试",
    )

    db_session.add(invalid_request)

    with pytest.raises(IntegrityError):
        db_session.flush()

    db_session.rollback()


def test_reject_approved_amount_greater_than_requested_amount(
    db_session: Session,
) -> None:
    """An approved refund amount cannot exceed the requested amount."""

    user = User(
        external_id="crm-user-refund-amount-30003",
        display_name="批准金额测试用户",
    )

    membership_account = MembershipAccount(
        user=user,
        membership_number="MBR-REFUND-AMOUNT-30003",
    )

    order = Order(
        membership_account=membership_account,
        order_number="ORD-REFUND-AMOUNT-30003",
        total_amount=Decimal("100.00"),
    )

    db_session.add(user)
    db_session.flush()

    invalid_request = RefundRequest(
        order_id=order.id,
        request_number="REF-REFUND-AMOUNT-30003",
        requested_amount=Decimal("30.00"),
        approved_amount=Decimal("50.00"),
        reason="批准金额超过申请金额",
    )

    db_session.add(invalid_request)

    with pytest.raises(IntegrityError):
        db_session.flush()

    db_session.rollback()


def test_create_chat_thread_with_ordered_messages(
    db_session: Session,
) -> None:
    """A chat thread owns ordered messages with roles and citations."""

    user = User(
        external_id="crm-user-chat-40001",
        display_name="聊天测试用户",
    )

    thread = ChatThread(
        user=user,
        title="退款政策咨询",
        subject=ChatSubject.REFUND,
        metadata_={
            "source": "web",
            "locale": "zh-CN",
        },
    )

    user_message = ChatMessage(
        thread=thread,
        sequence_number=1,
        role=ChatMessageRole.USER,
        content="普通会员签收后多久可以申请退款？",
        status=ChatMessageStatus.COMPLETED,
    )

    assistant_message = ChatMessage(
        thread=thread,
        sequence_number=2,
        role=ChatMessageRole.ASSISTANT,
        content="请根据当前有效退款政策判断。",
        status=ChatMessageStatus.COMPLETED,
        citations=[
            {
                "document_id": "document-001",
                "document_version_id": "version-003",
                "chunk_id": "chunk-007",
                "quote": "普通会员签收后 7 天内可以申请退款。",
            }
        ],
        metadata_={
            "model": "mock-model",
            "prompt_version": "v1",
        },
    )

    db_session.add(user)
    db_session.flush()

    assert isinstance(thread.id, UUID)
    assert isinstance(user_message.id, UUID)
    assert isinstance(assistant_message.id, UUID)
    assert thread.user is user
    assert user.chat_threads == [thread]
    assert user_message.thread is thread
    assert assistant_message.thread is thread
    assert thread.messages == [
        user_message,
        assistant_message,
    ]
    assert [
        message.sequence_number
        for message in thread.messages
    ] == [1, 2]
    assert thread.status is ChatThreadStatus.ACTIVE
    assert thread.subject is ChatSubject.REFUND
    assert user_message.role is ChatMessageRole.USER
    assert assistant_message.role is ChatMessageRole.ASSISTANT
    assert user_message.status is ChatMessageStatus.COMPLETED
    assert assistant_message.citations == [
        {
            "document_id": "document-001",
            "document_version_id": "version-003",
            "chunk_id": "chunk-007",
            "quote": "普通会员签收后 7 天内可以申请退款。",
        }
    ]
    assert thread.metadata_ == {
        "source": "web",
        "locale": "zh-CN",
    }


def test_reject_duplicate_message_sequence_number(
    db_session: Session,
) -> None:
    """One thread cannot have two messages with the same sequence number."""

    user = User(
        external_id="crm-user-chat-40002",
        display_name="重复消息序号用户",
    )

    thread = ChatThread(user=user)

    first_message = ChatMessage(
        thread=thread,
        sequence_number=1,
        role=ChatMessageRole.USER,
        content="第一条消息。",
    )

    db_session.add(user)
    db_session.flush()

    duplicate_message = ChatMessage(
        thread_id=thread.id,
        sequence_number=1,
        role=ChatMessageRole.ASSISTANT,
        content="错误地重复使用第一条消息序号。",
    )

    db_session.add(duplicate_message)

    with pytest.raises(IntegrityError):
        db_session.flush()

    db_session.rollback()


@pytest.mark.parametrize("invalid_sequence_number", [0, -1])
def test_reject_non_positive_message_sequence_number(
    db_session: Session,
    invalid_sequence_number: int,
) -> None:
    """A chat message sequence number must be greater than zero."""

    user = User(
        external_id=f"crm-user-chat-sequence-{abs(invalid_sequence_number)}",
        display_name="消息序号测试用户",
    )

    thread = ChatThread(user=user)

    db_session.add(user)
    db_session.flush()

    invalid_message = ChatMessage(
        thread_id=thread.id,
        sequence_number=invalid_sequence_number,
        role=ChatMessageRole.USER,
        content="非法消息序号测试内容。",
    )

    db_session.add(invalid_message)

    with pytest.raises(IntegrityError):
        db_session.flush()

    db_session.rollback()


def test_reject_blank_chat_message_content(
    db_session: Session,
) -> None:
    """A chat message cannot contain only whitespace."""

    user = User(
        external_id="crm-user-chat-40003",
        display_name="空消息测试用户",
    )

    thread = ChatThread(user=user)

    db_session.add(user)
    db_session.flush()

    invalid_message = ChatMessage(
        thread_id=thread.id,
        sequence_number=1,
        role=ChatMessageRole.USER,
        content="   ",
    )

    db_session.add(invalid_message)

    with pytest.raises(IntegrityError):
        db_session.flush()

    db_session.rollback()


def test_archive_chat_thread_without_deleting_messages(
    db_session: Session,
) -> None:
    """A thread can be archived while keeping its message history."""

    user = User(
        external_id="crm-user-chat-40004",
        display_name="归档线程测试用户",
    )

    thread = ChatThread(
        user=user,
        status=ChatThreadStatus.ARCHIVED,
        subject=ChatSubject.GENERAL,
    )

    message = ChatMessage(
        thread=thread,
        sequence_number=1,
        role=ChatMessageRole.SYSTEM,
        content="对话已归档。",
        status=ChatMessageStatus.COMPLETED,
    )

    db_session.add(user)
    db_session.flush()

    assert thread.status is ChatThreadStatus.ARCHIVED
    assert message in thread.messages
    assert message.status is ChatMessageStatus.COMPLETED