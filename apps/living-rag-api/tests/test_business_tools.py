from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.membership_account import (
    MembershipAccount,
    MembershipTier,
)
from app.models.order import Order, OrderStatus
from app.models.user import User
from app.services.business_tools import get_order
from datetime import datetime, timezone

from app.models.membership_account import (
    MembershipAccount,
    MembershipAccountStatus,
    MembershipTier,
)
from app.models.refund_request import (
    RefundRequest,
    RefundRequestStatus,
)
from app.models.user import User, UserStatus
from app.services.business_tools import (
    get_membership,
    get_refund_history,
    get_user,
)

def _create_order(
    db_session: Session,
    *,
    order_number: str,
    status: OrderStatus,
    metadata: dict,
) -> Order:
    """Create an isolated user, membership account, and order for one test."""

    user = User(
        external_id=f"test-{order_number}-user",
        email=f"{order_number.lower()}@example.com",
        display_name=f"Test User {order_number}",
    )

    membership_account = MembershipAccount(
        user=user,
        membership_number=f"TEST-{order_number}",
        tier=MembershipTier.STANDARD,
    )

    order = Order(
        membership_account=membership_account,
        order_number=order_number,
        status=status,
        total_amount=Decimal("199.00"),
        metadata_=metadata,
    )

    db_session.add(user)
    db_session.flush()

    return order


def test_get_order_returns_received_order(
    db_session: Session,
) -> None:
    """A received order should return its facts and is_received=True."""

    _create_order(
        db_session,
        order_number="O2025001",
        status=OrderStatus.COMPLETED,
        metadata={
            "received_at": "2026-01-05T14:30:00+08:00",
            "returnable": True,
            "product_name": "智能保温杯",
            "designated_free_return": False,
            "campaign_tags": [],
        },
    )

    result = get_order(db_session, "O2025001")

    assert result["found"] is True
    assert result["order_number"] == "O2025001"
    assert result["status"] == "completed"
    assert result["received_at"] == "2026-01-05T14:30:00+08:00"
    assert result["is_received"] is True
    assert result["returnable"] is True
    assert result["product_name"] == "智能保温杯"
    assert result["designated_free_return"] is False
    assert result["campaign_tags"] == []


def test_get_order_returns_unreceived_order(
    db_session: Session,
) -> None:
    """An existing order without received_at should be found but unreceived."""

    _create_order(
        db_session,
        order_number="O2025005",
        status=OrderStatus.SHIPPED,
        metadata={
            "returnable": True,
            "product_name": "无线鼠标",
            "shipping_status": "in_transit",
        },
    )

    result = get_order(db_session, "O2025005")

    assert result["found"] is True
    assert result["order_number"] == "O2025005"
    assert result["status"] == "shipped"
    assert result["received_at"] is None
    assert result["is_received"] is False
    assert result["returnable"] is True
    assert result["product_name"] == "无线鼠标"
    assert result["shipping_status"] == "in_transit"


def test_get_order_returns_not_found_for_unknown_order(
    db_session: Session,
) -> None:
    """An unknown order number should return a structured not-found result."""

    result = get_order(db_session, "O2025999")

    assert result["found"] is False
    assert result["order_number"] == "O2025999"
    assert result["error"] == "order_not_found"
    assert result["message"] == "未找到订单 O2025999"


def test_get_user_returns_user_facts(
    db_session: Session,
) -> None:
    """An existing business user ID should return user facts."""

    user = User(
        external_id="USR-TEST-001",
        email="test-user@example.com",
        display_name="测试用户",
        status=UserStatus.ACTIVE,
        metadata_={
            "source": "pytest",
        },
    )

    db_session.add(user)
    db_session.flush()

    result = get_user(db_session, "USR-TEST-001")

    assert result["found"] is True
    assert result["user_id"] == "USR-TEST-001"
    assert result["external_id"] == "USR-TEST-001"
    assert result["database_id"] == str(user.id)
    assert result["email"] == "test-user@example.com"
    assert result["display_name"] == "测试用户"
    assert result["status"] == "active"
    assert result["metadata"] == {
        "source": "pytest",
    }


def test_get_user_returns_not_found_for_unknown_user(
    db_session: Session,
) -> None:
    """An unknown external user ID should return a structured error."""

    result = get_user(db_session, "USR-UNKNOWN")

    assert result["found"] is False
    assert result["user_id"] == "USR-UNKNOWN"
    assert result["error"] == "user_not_found"


def test_get_membership_returns_active_gold_membership(
    db_session: Session,
) -> None:
    """Membership lookup should return both tier and account status."""

    user = User(
        external_id="USR-TEST-002",
        display_name="金卡测试用户",
    )

    membership = MembershipAccount(
        user=user,
        membership_number="M-TEST-002",
        tier=MembershipTier.GOLD,
        status=MembershipAccountStatus.ACTIVE,
        points=1200,
    )

    db_session.add(user)
    db_session.flush()

    result = get_membership(db_session, "USR-TEST-002")

    assert result["found"] is True
    assert result["user_id"] == "USR-TEST-002"
    assert result["membership_id"] == str(membership.id)
    assert result["membership_number"] == "M-TEST-002"
    assert result["tier"] == "gold"
    assert result["status"] == "active"
    assert result["points"] == 1200


def test_get_membership_preserves_suspended_status(
    db_session: Session,
) -> None:
    """A suspended gold account must not be treated as an active gold account."""

    user = User(
        external_id="USR-TEST-003",
        display_name="冻结金卡用户",
    )

    membership = MembershipAccount(
        user=user,
        membership_number="M-TEST-003",
        tier=MembershipTier.GOLD,
        status=MembershipAccountStatus.SUSPENDED,
    )

    db_session.add(user)
    db_session.flush()

    result = get_membership(db_session, "USR-TEST-003")

    assert result["found"] is True
    assert result["tier"] == "gold"
    assert result["status"] == "suspended"
    assert result["status"] != "active"


def test_get_membership_returns_not_found_without_membership(
    db_session: Session,
) -> None:
    """An existing user without a membership account should be explicit."""

    user = User(
        external_id="USR-TEST-004",
        display_name="无会员用户",
    )

    db_session.add(user)
    db_session.flush()

    result = get_membership(db_session, "USR-TEST-004")

    assert result["found"] is False
    assert result["user_id"] == "USR-TEST-004"
    assert result["error"] == "membership_not_found"


def test_get_refund_history_returns_multiple_requests(
    db_session: Session,
) -> None:
    """Refund history should return all requests ordered by requested_at."""

    order = _create_order(
        db_session,
        order_number="O-REFUND-001",
        status=OrderStatus.COMPLETED,
        metadata={
            "returnable": True,
        },
    )

    first_request = RefundRequest(
        order=order,
        request_number="R-REFUND-001",
        status=RefundRequestStatus.REJECTED,
        requested_amount=Decimal("199.00"),
        reason="第一次申请",
        requested_at=datetime(
            2026,
            1,
            10,
            tzinfo=timezone.utc,
        ),
    )

    second_request = RefundRequest(
        order=order,
        request_number="R-REFUND-002",
        status=RefundRequestStatus.COMPLETED,
        requested_amount=Decimal("199.00"),
        approved_amount=Decimal("199.00"),
        reason="第二次申请",
        requested_at=datetime(
            2026,
            1,
            12,
            tzinfo=timezone.utc,
        ),
        completed_at=datetime(
            2026,
            1,
            15,
            tzinfo=timezone.utc,
        ),
    )

    db_session.add_all([first_request, second_request])
    db_session.flush()

    result = get_refund_history(
        db_session,
        "O-REFUND-001",
    )

    assert result["found"] is True
    assert result["order_number"] == "O-REFUND-001"
    assert len(result["refund_requests"]) == 2
    assert result["refund_requests"][0]["status"] == "rejected"
    assert result["refund_requests"][1]["status"] == "completed"
    assert result["refund_requests"][1]["approved_amount"] == Decimal(
        "199.00"
    )
    assert result["refund_requests"][1]["completed_at"] is not None


def test_get_refund_history_returns_empty_list_without_requests(
    db_session: Session,
) -> None:
    """An existing order without refund requests should return an empty list."""

    _create_order(
        db_session,
        order_number="O-REFUND-002",
        status=OrderStatus.SHIPPED,
        metadata={
            "shipping_status": "in_transit",
        },
    )

    result = get_refund_history(
        db_session,
        "O-REFUND-002",
    )

    assert result["found"] is True
    assert result["order_number"] == "O-REFUND-002"
    assert result["refund_requests"] == []


def test_get_refund_history_returns_not_found_for_unknown_order(
    db_session: Session,
) -> None:
    """Refund history lookup should distinguish an unknown order."""

    result = get_refund_history(
        db_session,
        "O-REFUND-UNKNOWN",
    )

    assert result["found"] is False
    assert result["error"] == "order_not_found"