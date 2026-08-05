from datetime import datetime


def evaluate_refund_eligibility(
    order: dict,
    membership: dict,
    refund_history: dict,
    *,
    as_of: datetime,
    refund_window_days: int = 15,
    conflict_blocking: bool = False,
) -> dict:
    """Evaluate refund eligibility using deterministic Python rules."""

    if not order.get("found", False):
        return {
            "eligible": False,
            "decision": "not_found",
            "reason": "订单不存在",
            "requires_manual_review": False,
        }

    if not membership.get("found", False):
        return {
            "eligible": False,
            "decision": "manual_review",
            "reason": "会员信息缺失，无法完成资格判断",
            "requires_manual_review": True,
        }

    if not refund_history.get("found", False):
        return {
            "eligible": False,
            "decision": "manual_review",
            "reason": "订单与退款历史查询结果不一致",
            "requires_manual_review": True,
        }

    refund_requests = refund_history.get(
        "refund_requests",
        [],
    )

    already_refunded = any(
        item.get("status") == "completed"
        for item in refund_requests
    )

    if already_refunded:
        return {
            "eligible": False,
            "decision": "ineligible",
            "reason": "订单已经完成退款，不能重复申请",
            "requires_manual_review": False,
        }

    if membership.get("status") != "active":
        return {
            "eligible": False,
            "decision": "manual_review",
            "reason": "会员账号当前状态异常",
            "requires_manual_review": True,
        }

    if not order.get("is_received", False):
        return {
            "eligible": False,
            "decision": "not_ready",
            "reason": "订单尚未签收，暂时无法计算退款期限",
            "requires_manual_review": False,
        }

    if not order.get("returnable", False):
        return {
            "eligible": False,
            "decision": "ineligible",
            "reason": "商品不符合退货条件",
            "requires_manual_review": False,
        }

    received_at_value = order.get("received_at")

    if received_at_value is None:
        return {
            "eligible": False,
            "decision": "manual_review",
            "reason": "订单标记为已签收，但缺少签收时间",
            "requires_manual_review": True,
        }

    if isinstance(received_at_value, datetime):
        received_at = received_at_value
    else:
        received_at = datetime.fromisoformat(
            str(received_at_value)
        )

    if as_of < received_at:
        return {
            "eligible": False,
            "decision": "manual_review",
            "reason": "判断时间早于订单签收时间，订单时间数据异常",
            "requires_manual_review": True,
        }

    elapsed_days = (
        as_of - received_at
    ).days

    if elapsed_days > refund_window_days:
        return {
            "eligible": False,
            "decision": "ineligible",
            "reason": "已超过当前退款期限",
            "elapsed_days": elapsed_days,
            "refund_window_days": refund_window_days,
            "requires_manual_review": False,
        }

    if conflict_blocking:
        return {
            "eligible": False,
            "decision": "manual_review",
            "reason": "当前政策存在影响退款结论的未决冲突",
            "elapsed_days": elapsed_days,
            "refund_window_days": refund_window_days,
            "requires_manual_review": True,
        }

    is_free_return_member = membership.get(
        "tier"
    ) in {"gold", "platinum"}

    is_designated_free_return = order.get(
        "designated_free_return",
        False,
    )

    if (
        is_free_return_member
        and is_designated_free_return
    ):
        return_shipping_payer = "platform"
    else:
        return_shipping_payer = "customer"

    return {
        "eligible": True,
        "decision": "eligible",
        "reason": "订单符合当前退款条件",
        "elapsed_days": elapsed_days,
        "refund_window_days": refund_window_days,
        "return_shipping_payer": return_shipping_payer,
        "requires_manual_review": False,
    }