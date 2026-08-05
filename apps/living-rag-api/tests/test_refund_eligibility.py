from datetime import datetime, timedelta, timezone

import pytest

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


def _order(
    *,
    received_at: str,
    designated_free_return: bool = False,
    returnable: bool = True,
    is_received: bool = True,
) -> dict:
    return {
        "found": True,
        "order_number": "TEST-ORDER",
        "status": "completed",
        "received_at": received_at,
        "is_received": is_received,
        "returnable": returnable,
        "designated_free_return": designated_free_return,
    }


def _membership(
    *,
    tier: str = "standard",
    status: str = "active",
) -> dict:
    return {
        "found": True,
        "user_id": "USR-TEST",
        "tier": tier,
        "status": status,
    }


def _refund_history(*statuses: str) -> dict:
    return {
        "found": True,
        "order_number": "TEST-ORDER",
        "refund_requests": [
            {"status": status}
            for status in statuses
        ],
    }


def test_standard_member_can_apply_with_customer_shipping(
    ) -> None:
    result = evaluate_refund_eligibility(
        _order(
            received_at="2026-01-09T10:00:00+08:00",
        ),
        _membership(),
        _refund_history(),
        as_of=AS_OF,
    )

    assert result["eligible"] is True
    assert result["decision"] == "eligible"
    assert result["elapsed_days"] == 12
    assert result["return_shipping_payer"] == "customer"
    assert result["requires_manual_review"] is False


def test_gold_member_with_designated_product_gets_free_return(
    ) -> None:
    result = evaluate_refund_eligibility(
        _order(
            received_at="2026-01-07T10:00:00+08:00",
            designated_free_return=True,
        ),
        _membership(tier="gold"),
        _refund_history(),
        as_of=AS_OF,
    )

    assert result["eligible"] is True
    assert result["decision"] == "eligible"
    assert result["elapsed_days"] == 14
    assert result["return_shipping_payer"] == "platform"


def test_order_over_refund_window_is_ineligible(
    ) -> None:
    result = evaluate_refund_eligibility(
        _order(
            received_at="2026-01-03T10:00:00+08:00",
        ),
        _membership(tier="silver"),
        _refund_history(),
        as_of=AS_OF,
    )

    assert result["eligible"] is False
    assert result["decision"] == "ineligible"
    assert result["elapsed_days"] == 18
    assert result["refund_window_days"] == 15
    assert result["requires_manual_review"] is False


def test_completed_refund_rejects_duplicate_request(
    ) -> None:
    result = evaluate_refund_eligibility(
        _order(
            received_at="2026-01-09T10:00:00+08:00",
        ),
        _membership(tier="silver"),
        _refund_history("completed"),
        as_of=AS_OF,
    )

    assert result["eligible"] is False
    assert result["decision"] == "ineligible"
    assert result["reason"] == "订单已经完成退款，不能重复申请"
    assert result["requires_manual_review"] is False


def test_unreceived_order_is_not_ready(
    ) -> None:
    result = evaluate_refund_eligibility(
        _order(
            received_at="",
            is_received=False,
        ),
        _membership(),
        _refund_history(),
        as_of=AS_OF,
    )

    assert result["eligible"] is False
    assert result["decision"] == "not_ready"
    assert result["requires_manual_review"] is False


def test_suspended_membership_requires_manual_review(
    ) -> None:
    result = evaluate_refund_eligibility(
        _order(
            received_at="2026-01-09T10:00:00+08:00",
            designated_free_return=True,
        ),
        _membership(
            tier="gold",
            status="suspended",
        ),
        _refund_history(),
        as_of=AS_OF,
    )

    assert result["eligible"] is False
    assert result["decision"] == "manual_review"
    assert result["requires_manual_review"] is True


def test_blocking_policy_conflict_requires_manual_review(
    ) -> None:
    result = evaluate_refund_eligibility(
        _order(
            received_at="2026-01-09T10:00:00+08:00",
        ),
        _membership(),
        _refund_history(),
        as_of=AS_OF,
        conflict_blocking=True,
    )

    assert result["eligible"] is False
    assert result["decision"] == "manual_review"
    assert result["requires_manual_review"] is True


@pytest.mark.parametrize(
    ("order", "membership", "refund_history", "decision"),
    [
        (
            {"found": False},
            _membership(),
            _refund_history(),
            "not_found",
        ),
        (
            _order(received_at="2026-01-09T10:00:00+08:00"),
            {"found": False},
            _refund_history(),
            "manual_review",
        ),
        (
            _order(received_at="2026-01-09T10:00:00+08:00"),
            _membership(),
            {"found": False},
            "manual_review",
        ),
    ],
)
def test_missing_required_facts_use_safe_decisions(
    order: dict,
    membership: dict,
    refund_history: dict,
    decision: str,
) -> None:
    result = evaluate_refund_eligibility(
        order,
        membership,
        refund_history,
        as_of=AS_OF,
    )

    assert result["eligible"] is False
    assert result["decision"] == decision
