"""Service for creating deterministic refund requests."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.audit_log import (
    AuditActorType,
    AuditLog,
    AuditResult,
)
from app.models.membership_account import MembershipAccount
from app.models.order import Order
from app.models.refund_request import (
    RefundRequest,
    RefundRequestStatus,
)
from app.models.user import User
from app.services.business_tools import (
    get_order,
    get_refund_history,
)
from app.services.refund_eligibility import (
    evaluate_refund_eligibility,
)


def _build_membership_facts(
    membership: MembershipAccount,
) -> dict[str, object]:
    """Convert a membership ORM object into rule-service facts."""

    return {
        "found": True,
        "user_id": str(membership.user_id),
        "membership_id": str(membership.id),
        "membership_number": membership.membership_number,
        "tier": membership.tier.value,
        "status": membership.status.value,
        "points": membership.points,
        "started_at": membership.started_at,
        "expires_at": membership.expires_at,
        "metadata": membership.metadata_,
    }


def _build_audit_log(
    *,
    actor_id: UUID,
    action: str,
    resource_id: UUID,
    result: AuditResult,
    reason: str,
    trace_id: UUID,
    before_snapshot: dict[str, object],
    after_snapshot: dict[str, object],
    metadata: dict[str, object],
) -> AuditLog:
    """Build one audit record for the refund request decision."""

    return AuditLog(
        actor_type=AuditActorType.USER,
        actor_id=actor_id,
        action=action,
        resource_type="refund_request",
        resource_id=resource_id,
        result=result,
        reason=reason,
        before_snapshot=before_snapshot,
        after_snapshot=after_snapshot,
        trace_id=trace_id,
        metadata_=metadata,
    )


def _build_denied_result(
    *,
    db: Session,
    order: Order,
    user_id: UUID,
    trace_id: UUID,
    decision: dict[str, object],
) -> dict[str, object]:
    """Write a denied refund audit record and return the decision."""

    reason = str(
        decision.get(
            "reason",
            "退款申请未通过当前资格判断。",
        ),
    )

    audit_log = _build_audit_log(
        actor_id=user_id,
        action="refund_request_denied",
        resource_id=order.id,
        result=AuditResult.DENIED,
        reason=reason,
        trace_id=trace_id,
        before_snapshot={},
        after_snapshot={
            "created": False,
            "decision": decision.get("decision"),
            "requires_manual_review": decision.get(
                "requires_manual_review",
                False,
            ),
        },
        metadata={
            "order_number": order.order_number,
        },
    )

    db.add(audit_log)
    db.flush()

    return {
        "created": False,
        "decision": decision.get("decision"),
        "reason": reason,
        "requires_manual_review": decision.get(
            "requires_manual_review",
            False,
        ),
        "refund_request_id": None,
        "request_number": None,
        "requested_amount": None,
        "return_shipping_payer": None,
        "order_number": order.order_number,
    }


def create_refund_request(
    db: Session,
    *,
    order_number: str,
    user_id: UUID,
    reason: str,
    trace_id: UUID,
    as_of: datetime,
    conflict_blocking: bool = False,
    refund_window_days: int = 15,
) -> dict[str, object]:
    """Create a pending refund request only when rules allow it."""

    normalized_order_number = order_number.strip().upper()
    normalized_reason = reason.strip()

    if not normalized_order_number:
        raise ValueError(
            "Order number cannot be empty."
        )

    if not normalized_reason:
        raise ValueError(
            "Refund request reason cannot be empty."
        )

    statement = (
        select(Order, MembershipAccount)
        .join(
            MembershipAccount,
            MembershipAccount.id == Order.membership_account_id,
        )
        .where(
            Order.order_number == normalized_order_number,
            MembershipAccount.user_id == user_id,
        )
    )

    row = db.execute(statement).first()

    if row is None:
        return {
            "created": False,
            "decision": "not_found",
            "reason": (
                f"未找到属于当前用户的订单 "
                f"{normalized_order_number}。"
            ),
            "requires_manual_review": False,
            "refund_request_id": None,
            "request_number": None,
            "requested_amount": None,
            "return_shipping_payer": None,
            "order_number": normalized_order_number,
        }

    order, membership = row

    order_facts = get_order(
        db,
        normalized_order_number,
    )

    membership_facts = _build_membership_facts(
        membership,
    )

    refund_history = get_refund_history(
        db,
        normalized_order_number,
    )

    eligibility = evaluate_refund_eligibility(
        order_facts,
        membership_facts,
        refund_history,
        as_of=as_of,
        refund_window_days=refund_window_days,
        conflict_blocking=conflict_blocking,
    )

    if not eligibility.get("eligible", False):
        return _build_denied_result(
            db=db,
            order=order,
            user_id=user_id,
            trace_id=trace_id,
            decision=eligibility,
        )

    request_number = (
        f"R{uuid4().hex[:12].upper()}"
    )

    refund_request = RefundRequest(
        order_id=order.id,
        request_number=request_number,
        status=RefundRequestStatus.PENDING,
        requested_amount=order.total_amount,
        reason=normalized_reason,
        metadata_={
            "order_number": normalized_order_number,
            "eligibility_decision": eligibility.get(
                "decision",
            ),
            "elapsed_days": eligibility.get(
                "elapsed_days",
            ),
            "refund_window_days": eligibility.get(
                "refund_window_days",
            ),
            "return_shipping_payer": eligibility.get(
                "return_shipping_payer",
            ),
            "trace_id": str(trace_id),
        },
    )

    db.add(refund_request)
    db.flush()

    audit_log = _build_audit_log(
        actor_id=user_id,
        action="create_refund_request",
        resource_id=refund_request.id,
        result=AuditResult.PENDING,
        reason=normalized_reason,
        trace_id=trace_id,
        before_snapshot={},
        after_snapshot={
            "status": RefundRequestStatus.PENDING.value,
            "request_number": request_number,
            "requested_amount": str(
                Decimal(order.total_amount),
            ),
            "return_shipping_payer": eligibility.get(
                "return_shipping_payer",
            ),
        },
        metadata={
            "order_number": normalized_order_number,
            "membership_tier": membership.tier.value,
        },
    )

    db.add(audit_log)
    db.flush()

    return {
        "created": True,
        "decision": eligibility.get("decision"),
        "reason": eligibility.get(
            "reason",
            "订单符合当前退款条件。",
        ),
        "requires_manual_review": False,
        "refund_request_id": refund_request.id,
        "request_number": request_number,
        "requested_amount": order.total_amount,
        "return_shipping_payer": eligibility.get(
            "return_shipping_payer",
        ),
        "order_number": normalized_order_number,
    }