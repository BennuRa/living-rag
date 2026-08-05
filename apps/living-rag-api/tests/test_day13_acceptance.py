from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.membership_account import (
    MembershipAccount,
    MembershipAccountStatus,
    MembershipTier,
)
from app.models.order import Order, OrderStatus
from app.models.refund_request import (
    RefundRequest,
    RefundRequestStatus,
)
from app.models.user import User
from app.services.business_tools import (
    get_membership,
    get_order,
    get_refund_history,
)
from app.services.refund_eligibility import (
    evaluate_refund_eligibility,
)


CHINA_TZ = timezone(timedelta(hours=8))
AS_OF = datetime(
    2026,
    1,
    21,
    10,
    0,
    tzinfo=CHINA_TZ,
)


def _create_demo_order(
    db_session: Session,
    *,
    order_number: str,
    user_number: str,
    tier: MembershipTier,
    membership_status: MembershipAccountStatus,
    order_status: OrderStatus,
    received_at: str | None,
    designated_free_return: bool = False,
    refund_status: RefundRequestStatus | None = None,
) -> None:
    user = User(
        external_id=user_number,
        display_name=f"Day 13 {order_number}",
    )

    membership = MembershipAccount(
        user=user,
        membership_number=f"M-{order_number}",
        tier=tier,
        status=membership_status,
    )

    metadata: dict[str, object] = {
        "returnable": True,
        "product_name": f"Product {order_number}",
        "designated_free_return": designated_free_return,
    }

    if received_at is not None:
        metadata["received_at"] = received_at
    else:
        metadata["shipping_status"] = "in_transit"

    order = Order(
        membership_account=membership,
        order_number=order_number,
        status=order_status,
        total_amount=Decimal("199.00"),
        metadata_=metadata,
    )

    db_session.add(user)
    db_session.flush()

    if refund_status is not None:
        refund_request = RefundRequest(
            order=order,
            request_number=f"R-{order_number}",
            status=refund_status,
            requested_amount=Decimal("199.00"),
            approved_amount=(
                Decimal("199.00")
                if refund_status is RefundRequestStatus.COMPLETED
                else None
            ),
            reason="Day 13 acceptance fixture",
            completed_at=(
                AS_OF
                if refund_status is RefundRequestStatus.COMPLETED
                else None
            ),
        )
        db_session.add(refund_request)
        db_session.flush()


def _evaluate_order(
    db_session: Session,
    *,
    order_number: str,
    user_number: str,
) -> dict:
    order = get_order(db_session, order_number)
    membership = get_membership(db_session, user_number)
    refund_history = get_refund_history(db_session, order_number)

    return evaluate_refund_eligibility(
        order,
        membership,
        refund_history,
        as_of=AS_OF,
    )


def test_day13_o2025001_is_eligible_with_customer_shipping(
    db_session: Session,
) -> None:
    _create_demo_order(
        db_session,
        order_number="O2025001",
        user_number="USR001",
        tier=MembershipTier.STANDARD,
        membership_status=MembershipAccountStatus.ACTIVE,
        order_status=OrderStatus.COMPLETED,
        received_at="2026-01-09T10:00:00+08:00",
    )

    result = _evaluate_order(
        db_session,
        order_number="O2025001",
        user_number="USR001",
    )

    assert result["eligible"] is True
    assert result["decision"] == "eligible"
    assert result["elapsed_days"] == 12
    assert result["return_shipping_payer"] == "customer"


def test_day13_o2025002_is_eligible_with_platform_shipping(
    db_session: Session,
) -> None:
    _create_demo_order(
        db_session,
        order_number="O2025002",
        user_number="USR002",
        tier=MembershipTier.GOLD,
        membership_status=MembershipAccountStatus.ACTIVE,
        order_status=OrderStatus.COMPLETED,
        received_at="2026-01-07T10:00:00+08:00",
        designated_free_return=True,
    )

    result = _evaluate_order(
        db_session,
        order_number="O2025002",
        user_number="USR002",
    )

    assert result["eligible"] is True
    assert result["decision"] == "eligible"
    assert result["elapsed_days"] == 14
    assert result["return_shipping_payer"] == "platform"


def test_day13_o2025003_is_outside_current_window(
    db_session: Session,
) -> None:
    _create_demo_order(
        db_session,
        order_number="O2025003",
        user_number="USR003",
        tier=MembershipTier.SILVER,
        membership_status=MembershipAccountStatus.ACTIVE,
        order_status=OrderStatus.COMPLETED,
        received_at="2026-01-03T10:00:00+08:00",
    )

    result = _evaluate_order(
        db_session,
        order_number="O2025003",
        user_number="USR003",
    )

    assert result["eligible"] is False
    assert result["decision"] == "ineligible"
    assert result["elapsed_days"] == 18
    assert result["refund_window_days"] == 15


def test_day13_o2025006_rejects_duplicate_refund(
    db_session: Session,
) -> None:
    _create_demo_order(
        db_session,
        order_number="O2025006",
        user_number="USR006",
        tier=MembershipTier.SILVER,
        membership_status=MembershipAccountStatus.ACTIVE,
        order_status=OrderStatus.REFUNDED,
        received_at="2026-01-09T10:00:00+08:00",
        refund_status=RefundRequestStatus.COMPLETED,
    )

    result = _evaluate_order(
        db_session,
        order_number="O2025006",
        user_number="USR006",
    )

    assert result["eligible"] is False
    assert result["decision"] == "ineligible"
    assert result["reason"] == "订单已经完成退款，不能重复申请"

