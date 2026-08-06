from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select

from app.models.audit_log import AuditLog
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
from app.services.refund_request_service import (
    create_refund_request,
)


def _create_order_case(
    db_session,
    *,
    external_id: str,
    order_number: str,
    received_at: str,
    tier: MembershipTier = MembershipTier.STANDARD,
    membership_status: MembershipAccountStatus = (
        MembershipAccountStatus.ACTIVE
    ),
    with_completed_refund: bool = False,
) -> tuple[User, Order]:
    """Create an isolated order case for refund-request tests."""

    user = User(
        external_id=external_id,
        display_name=f"Refund Request User {external_id}",
    )

    membership = MembershipAccount(
        user=user,
        membership_number=f"M-{external_id}",
        tier=tier,
        status=membership_status,
    )

    order = Order(
        membership_account=membership,
        order_number=order_number,
        status=OrderStatus.COMPLETED,
        total_amount=Decimal("199.00"),
        metadata_={
            "received_at": received_at,
            "returnable": True,
            "product_name": "Test Product",
            "designated_free_return": (
                tier in {
                    MembershipTier.GOLD,
                    MembershipTier.PLATINUM,
                }
            ),
        },
    )

    db_session.add(user)
    db_session.flush()

    if with_completed_refund:
        completed_refund = RefundRequest(
            order=order,
            request_number=f"R-HISTORY-{order_number}",
            status=RefundRequestStatus.COMPLETED,
            requested_amount=Decimal("199.00"),
            approved_amount=Decimal("199.00"),
            reason="Previous completed refund.",
            completed_at=datetime(
                2026,
                1,
                10,
                tzinfo=UTC,
            ),
        )

        db_session.add(completed_refund)
        db_session.flush()

    return user, order


def test_eligible_order_creates_pending_refund_request(
    db_session,
) -> None:
    """A received order within 15 days should create a pending request."""

    user, order = _create_order_case(
        db_session,
        external_id="USR-REFUND-001",
        order_number="O2025001",
        received_at="2026-01-05T14:30:00+08:00",
    )

    trace_id = (
        "11111111-1111-1111-1111-111111111111"
    )

    result = create_refund_request(
        db_session,
        order_number=order.order_number,
        user_id=user.id,
        reason="I want to apply for a refund.",
        trace_id=trace_id,
        as_of=datetime(
            2026,
            1,
            17,
            tzinfo=UTC,
        ),
    )

    assert result["created"] is True
    assert result["decision"] == "eligible"
    assert result["refund_request_id"] is not None
    assert result["request_number"]
    assert result["requested_amount"] == Decimal("199.00")
    assert result["return_shipping_payer"] == "customer"

    refund_statement = select(RefundRequest).where(
        RefundRequest.id == result["refund_request_id"],
    )

    refund_request = db_session.scalar(refund_statement)

    assert refund_request is not None
    assert refund_request.status == RefundRequestStatus.PENDING
    assert refund_request.order_id == order.id
    assert refund_request.requested_amount == Decimal("199.00")
    assert refund_request.reason == (
        "I want to apply for a refund."
    )

    audit_statement = select(AuditLog).where(
        AuditLog.resource_id == refund_request.id,
        AuditLog.action == "create_refund_request",
    )

    audit_log = db_session.scalar(audit_statement)

    assert audit_log is not None
    assert audit_log.result.value == "pending"
    assert audit_log.actor_id == user.id


def test_expired_order_does_not_create_refund_request(
    db_session,
) -> None:
    """An order received more than 15 days ago must be rejected."""

    user, order = _create_order_case(
        db_session,
        external_id="USR-REFUND-002",
        order_number="O2025003",
        received_at="2026-01-03T10:00:00+08:00",
    )

    result = create_refund_request(
        db_session,
        order_number=order.order_number,
        user_id=user.id,
        reason="I want to apply for a refund.",
        trace_id=(
            "22222222-2222-2222-2222-222222222222"
        ),
        as_of=datetime(
            2026,
            1,
            21,
            tzinfo=UTC,
        ),
    )

    assert result["created"] is False
    assert result["decision"] == "ineligible"
    assert result["refund_request_id"] is None
    assert result["requires_manual_review"] is False

    refund_requests = db_session.scalars(
        select(RefundRequest).where(
            RefundRequest.order_id == order.id,
        ),
    ).all()

    assert refund_requests == []


def test_completed_refund_does_not_create_duplicate_request(
    db_session,
) -> None:
    """An already refunded order must not receive another request."""

    user, order = _create_order_case(
        db_session,
        external_id="USR-REFUND-003",
        order_number="O2025006",
        received_at="2025-12-25T12:30:00+08:00",
        with_completed_refund=True,
    )

    result = create_refund_request(
        db_session,
        order_number=order.order_number,
        user_id=user.id,
        reason="I want to apply for another refund.",
        trace_id=(
            "33333333-3333-3333-3333-333333333333"
        ),
        as_of=datetime(
            2026,
            1,
            17,
            tzinfo=UTC,
        ),
    )

    assert result["created"] is False
    assert result["decision"] == "ineligible"
    assert result["refund_request_id"] is None

    refund_requests = db_session.scalars(
        select(RefundRequest).where(
            RefundRequest.order_id == order.id,
        ),
    ).all()

    assert len(refund_requests) == 1
    assert refund_requests[0].status == (
        RefundRequestStatus.COMPLETED
    )


def test_suspended_membership_requires_manual_review(
    db_session,
) -> None:
    """A suspended membership must not create an automatic request."""

    user, order = _create_order_case(
        db_session,
        external_id="USR-REFUND-004",
        order_number="O2025007",
        received_at="2026-01-05T11:00:00+08:00",
        tier=MembershipTier.GOLD,
        membership_status=MembershipAccountStatus.SUSPENDED,
    )

    result = create_refund_request(
        db_session,
        order_number=order.order_number,
        user_id=user.id,
        reason="I want to use my gold membership benefit.",
        trace_id=(
            "44444444-4444-4444-4444-444444444444"
        ),
        as_of=datetime(
            2026,
            1,
            17,
            tzinfo=UTC,
        ),
    )

    assert result["created"] is False
    assert result["decision"] == "manual_review"
    assert result["requires_manual_review"] is True
    assert result["refund_request_id"] is None

    refund_requests = db_session.scalars(
        select(RefundRequest).where(
            RefundRequest.order_id == order.id,
        ),
    ).all()

    assert refund_requests == []

    audit_statement = select(AuditLog).where(
        AuditLog.resource_id == order.id,
        AuditLog.action == "refund_request_denied",
    )

    audit_log = db_session.scalar(audit_statement)

    assert audit_log is not None
    assert audit_log.result.value == "denied"
    assert audit_log.actor_id == user.id