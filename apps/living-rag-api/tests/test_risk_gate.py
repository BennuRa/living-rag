import pytest

from app.services.risk_gate import (
    RiskAction,
    classify_risk_action,
)


def test_eligibility_question_is_read_only() -> None:
    """An eligibility question must not create a business side effect."""

    decision = classify_risk_action(
        "O2025001 签收 12 天了，能退款吗？"
    )

    assert decision.action == RiskAction.READ_ONLY
    assert decision.intent == "order_membership"
    assert "不会修改业务数据" in decision.reason


def test_refund_application_creates_refund_request() -> None:
    """A normal refund request should create a refund request."""

    decision = classify_risk_action(
        "我要申请 O2025001 的退款"
    )

    assert decision.action == RiskAction.CREATE_REFUND_REQUEST
    assert decision.intent == "refund_request"
    assert "创建退款申请" in decision.reason


def test_direct_refund_requires_approval_task() -> None:
    """Direct refund must never be executed automatically."""

    decision = classify_risk_action(
        "直接退款 O2025001"
    )

    assert decision.action == RiskAction.CREATE_APPROVAL_TASK
    assert decision.intent == "high_risk_operation"
    assert "人工审批" in decision.reason


def test_high_risk_keyword_has_priority_over_refund_request() -> None:
    """Direct refund must not be misclassified as a normal refund request."""

    decision = classify_risk_action(
        "我要申请直接退款 O2025001"
    )

    assert decision.action == RiskAction.CREATE_APPROVAL_TASK
    assert decision.intent == "high_risk_operation"


def test_modify_policy_requires_approval_task() -> None:
    """Policy modification must require human approval."""

    decision = classify_risk_action(
        "把退款政策修改成 60 天"
    )

    assert decision.action == RiskAction.CREATE_APPROVAL_TASK
    assert decision.intent == "high_risk_operation"


def test_delete_document_requires_approval_task() -> None:
    """Document deletion must require human approval."""

    decision = classify_risk_action(
        "删除退款政策文档"
    )

    assert decision.action == RiskAction.CREATE_APPROVAL_TASK
    assert decision.intent == "high_risk_operation"


def test_policy_question_is_read_only() -> None:
    """A policy question should stay on the read-only route."""

    decision = classify_risk_action(
        "目前退款政策的有效期限是多少？"
    )

    assert decision.action == RiskAction.READ_ONLY
    assert decision.intent == "policy_qa"


def test_unknown_question_rejects_direct_execution() -> None:
    """Unknown requests must not trigger a business operation."""

    decision = classify_risk_action(
        "帮我处理一下这个事情"
    )

    assert decision.action == RiskAction.REJECT_DIRECT_EXECUTION
    assert decision.intent == "unknown"
    assert "不会执行任何业务动作" in decision.reason


def test_blank_question_raises_value_error() -> None:
    """Blank input must be rejected before keyword matching."""

    with pytest.raises(
        ValueError,
        match="Question must not be blank.",
    ):
        classify_risk_action("   ")


def test_english_direct_refund_requires_approval() -> None:
    """English high-risk requests must use the approval route too."""

    decision = classify_risk_action(
        "Issue refund directly for O2025001"
    )

    assert decision.action == RiskAction.CREATE_APPROVAL_TASK
    assert decision.intent == "high_risk_operation"