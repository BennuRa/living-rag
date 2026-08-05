from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.order import Order
from app.models.user import User
from app.models.membership_account import MembershipAccount
from app.models.refund_request import RefundRequest


def get_order(db: Session, order_no: str) -> dict:
    """Return order facts without making a refund eligibility decision."""

    statement = select(Order).where(
        Order.order_number == order_no
    )

    order = db.scalar(statement)

    if order is None:
        return {
            "found": False,
            "order_number": order_no,
            "error": "order_not_found",
            "message": f"未找到订单 {order_no}",
        }

    metadata = order.metadata_ or {}
    received_at = metadata.get("received_at")
    is_received = received_at is not None

    return {
        "found": True,
        "order_number": order.order_number,
        "status": order.status.value,
        "received_at": received_at,
        "is_received": is_received,
        "returnable": metadata.get("returnable", False),
        "product_name": metadata.get("product_name"),
        "designated_free_return": metadata.get(
            "designated_free_return",
            False,
        ),
        "campaign_tags": metadata.get("campaign_tags", []),
        "shipping_status": metadata.get("shipping_status"),
        "region_type": metadata.get("region_type"),
        "estimated_delay_days": metadata.get(
            "estimated_delay_days"
        ),
    }


def get_user(db: Session, user_id: str):
    """Return user facts without making a refund eligibility decision."""

    statement = select(User).where(
        User.external_id == user_id
    )

    user = db.scalar(statement)

    if user is None:
        return {
            "found": False,
            "user_id": user_id,
            "error": "user_not_found",
            "message": f"未找到用户 {user_id}",
        }

    return {
        "found": True,
        "user_id": user.external_id,
        "database_id": str(user.id),
        "external_id": user.external_id,
        "email": user.email,
        "display_name": user.display_name,
        "status": user.status.value,
        "metadata": user.metadata_,
    }


def get_membership(db: Session, user_id: str) -> dict:
    """Return membership facts without making a refund eligibility decision."""
    user_statement = select(User).where(
        User.external_id == user_id
    )

    user = db.scalar(user_statement)
    if user is None:
        return {
            "found": False,
            "user_id": user_id,
            "error": "user_not_found",
            "message": f"未找到用户 {user_id}",
        }
    membership_statement = select(
        MembershipAccount
    ).where(
        MembershipAccount.user_id == user.id
    )

    membership = db.scalar(membership_statement)
    if membership is None:
        return {
            "found": False,
            "user_id": user_id,
            "error": "membership_not_found",
            "message": f"未找到用户 {user_id} 的会员信息",
        }
    return {
        "found": True,
        "user_id": user.external_id,
        "membership_id": str(membership.id),
        "membership_number": membership.membership_number,
        "tier": membership.tier.value,
        "status": membership.status.value,
        "points": membership.points,
        "started_at": membership.started_at,
        "expires_at": membership.expires_at,
        "metadata": membership.metadata_,
    }


def get_refund_history(
    db: Session,
    order_no: str,
) -> dict:
    """Return refund request history for one order."""
    order_statement = select(Order).where(
        Order.order_number == order_no
    )

    order = db.scalar(order_statement)
    if order is None:
        return {
            "found": False,
            "order_number": order_no,
            "error": "order_not_found",
            "message": f"未找到订单 {order_no}",
        }
    refund_statement = select(
        RefundRequest
    ).where(
        RefundRequest.order_id == order.id
    ).order_by(
        RefundRequest.requested_at
    )
    refund_requests = db.scalars(
        refund_statement
    ).all()

    history = []
    for refund_request in refund_requests:
        history.append(
            {
                "request_number": refund_request.request_number,
                "status": refund_request.status.value,
                "requested_amount": refund_request.requested_amount,
                "approved_amount": refund_request.approved_amount,
                "reason": refund_request.reason,
                "rejection_reason": refund_request.rejection_reason,
                "requested_at": refund_request.requested_at,
                "reviewed_at": refund_request.reviewed_at,
                "completed_at": refund_request.completed_at,
                "metadata": refund_request.metadata_,
            }            
        )

    return {
        "found": True,
        "order_number": order.order_number,
        "refund_requests": history,
    }
    