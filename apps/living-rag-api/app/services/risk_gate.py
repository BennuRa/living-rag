"""Deterministic risk gate for business-operation requests."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from app.services.qa_state import Intent


class RiskAction(StrEnum):
    """Safe route selected for the user's request."""

    READ_ONLY = "read_only"
    CREATE_REFUND_REQUEST = "create_refund_request"
    CREATE_APPROVAL_TASK = "create_approval_task"
    REJECT_DIRECT_EXECUTION = "reject_direct_execution"


@dataclass(frozen=True)
class RiskDecision:
    """Deterministic decision made before any business side effect."""

    action: RiskAction
    intent: Intent
    reason: str


HIGH_RISK_KEYWORDS = (
    "直接退款",
    "强制退款",
    "修改政策",
    "修改退款政策",
    "修改退款规则",
    "删除政策",
    "删除退款政策",
    "删除政策文档",
    "删除文档",
    "删除知识库",
    "direct refund",
    "force refund",
    "modify policy",
    "modify refund policy",
    "modify refund rule",
    "delete policy",
    "delete document",
    "delete knowledge base",
    "issue refund directly",
)

REFUND_REQUEST_KEYWORDS = (
    "我要申请退款",
    "申请退款",
    "提交退款",
    "发起退款",
    "我要退货退款",
    "请求退款",
    "request a refund",
    "apply for refund",
    "submit refund",
    "request refund",
)

ORDER_MEMBERSHIP_KEYWORDS = (
    "订单",
    "订单号",
    "会员",
    "会员等级",
    "能退款吗",
    "可以退款吗",
    "符合退款条件吗",
    "我能退款吗",
    "退款资格",
    "谁承担运费",
    "order",
    "order number",
    "membership",
    "member",
    "eligible for a refund",
    "refund eligibility",
    "who pays shipping",
)

POLICY_KEYWORDS = (
    "政策",
    "规则",
    "时限",
    "期限",
    "退款条件",
    "退款运费",
    "退货条件",
    "配送政策",
    "退款标准",
    "policy",
    "rule",
    "window",
    "deadline",
    "refund condition",
    "refund policy",
    "shipping fee",
    "return condition",
)


def classify_risk_action(question: str) -> RiskDecision:
    """Classify a request before any business-side effect is executed."""

    normalized_question = question.strip().lower()

    if not normalized_question:
        raise ValueError("Question must not be blank.")

    has_high_risk_keyword = any(
        keyword in normalized_question
        for keyword in HIGH_RISK_KEYWORDS
    )

    has_modify_policy_pattern = (
        "修改" in normalized_question
        and (
            "政策" in normalized_question
            or "规则" in normalized_question
        )
    )

    has_delete_document_pattern = (
        "删除" in normalized_question
        and (
            "政策" in normalized_question
            or "文档" in normalized_question
            or "知识库" in normalized_question
        )
    )

    has_english_modify_policy_pattern = (
        "modify" in normalized_question
        and (
            "policy" in normalized_question
            or "rule" in normalized_question
        )
    )

    has_english_delete_document_pattern = (
        "delete" in normalized_question
        and (
            "policy" in normalized_question
            or "document" in normalized_question
            or "knowledge base" in normalized_question
        )
    )

    if (
        has_high_risk_keyword
        or has_modify_policy_pattern
        or has_delete_document_pattern
        or has_english_modify_policy_pattern
        or has_english_delete_document_pattern
    ):
        return RiskDecision(
            action=RiskAction.CREATE_APPROVAL_TASK,
            intent="high_risk_operation",
            reason="高风险业务操作必须经过人工审批。",
        )

    has_refund_request_keyword = any(
        keyword in normalized_question
        for keyword in REFUND_REQUEST_KEYWORDS
    )

    has_chinese_refund_request_pattern = (
        "申请" in normalized_question
        and "退款" in normalized_question
    )

    has_english_refund_request_pattern = (
        (
            "request" in normalized_question
            or "apply" in normalized_question
            or "submit" in normalized_question
        )
        and "refund" in normalized_question
    )

    if (
        has_refund_request_keyword
        or has_chinese_refund_request_pattern
        or has_english_refund_request_pattern
    ):
        return RiskDecision(
            action=RiskAction.CREATE_REFUND_REQUEST,
            intent="refund_request",
            reason="用户正在申请退款，需要创建退款申请。",
        )

    if any(
        keyword in normalized_question
        for keyword in ORDER_MEMBERSHIP_KEYWORDS
    ):
        return RiskDecision(
            action=RiskAction.READ_ONLY,
            intent="order_membership",
            reason="这是订单或会员资格查询，不会修改业务数据。",
        )

    if any(
        keyword in normalized_question
        for keyword in POLICY_KEYWORDS
    ):
        return RiskDecision(
            action=RiskAction.READ_ONLY,
            intent="policy_qa",
            reason="这是政策知识查询，不会修改业务数据。",
        )

    return RiskDecision(
        action=RiskAction.REJECT_DIRECT_EXECUTION,
        intent="unknown",
        reason="无法确认请求意图，系统不会执行任何业务动作。",
    )