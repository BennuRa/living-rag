"""Business action orchestration with deterministic risk gating."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.approval_task import ApprovalTaskType
from app.models.membership_account import MembershipAccount
from app.models.order import Order
from app.services.approval_task_service import create_approval_task
from app.services.business_tools import get_order, get_refund_history
from app.services.refund_eligibility import evaluate_refund_eligibility
from app.services.refund_request_service import create_refund_request
from app.services.risk_gate import (
    RiskAction,
    RiskDecision,
    classify_risk_action,
)


ORDER_NUMBER_PATTERN = re.compile(r"\bO\d+\b", re.IGNORECASE)


def _extract_order_number(question: str) -> str | None:
    """Extract an order number such as O2025001 from a question."""

    match = ORDER_NUMBER_PATTERN.search(question)
    return match.group(0).upper() if match else None


def _select_high_risk_task_type(question: str) -> ApprovalTaskType:
    """Map a high-risk request to its approval task type."""

    normalized_question = question.strip().lower()

    if (
        "直接退款" in normalized_question
        or "强制退款" in normalized_question
        or "direct refund" in normalized_question
        or "force refund" in normalized_question
        or "issue refund directly" in normalized_question
    ):
        return ApprovalTaskType.DIRECT_REFUND

    if (
        (
            "修改" in normalized_question
            and (
                "政策" in normalized_question
                or "规则" in normalized_question
            )
        )
        or "modify policy" in normalized_question
        or "modify refund policy" in normalized_question
        or "modify refund rule" in normalized_question
    ):
        return ApprovalTaskType.MODIFY_POLICY

    if (
        (
            "删除" in normalized_question
            and (
                "政策" in normalized_question
                or "文档" in normalized_question
                or "知识库" in normalized_question
            )
        )
        or "delete policy" in normalized_question
        or "delete document" in normalized_question
        or "delete knowledge base" in normalized_question
    ):
        return ApprovalTaskType.DELETE_DOCUMENT

    return ApprovalTaskType.DIRECT_REFUND


def _find_owned_order(
    db: Session,
    *,
    order_number: str,
    user_id: UUID,
) -> tuple[Order, MembershipAccount] | None:
    """Find an order and membership account owned by the user."""

    statement = (
        select(Order, MembershipAccount)
        .join(
            MembershipAccount,
            MembershipAccount.id == Order.membership_account_id,
        )
        .where(
            Order.order_number == order_number,
            MembershipAccount.user_id == user_id,
        )
    )

    row = db.execute(statement).first()
    return (row[0], row[1]) if row else None


def _build_business_facts(
    db: Session,
    *,
    order: Order,
    membership: MembershipAccount,
    as_of: datetime,
) -> dict[str, object]:
    """Build order, membership, history, and deterministic eligibility facts."""

    order_facts = get_order(db, order.order_number)
    membership_facts = {
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
    refund_history = get_refund_history(db, order.order_number)
    eligibility = evaluate_refund_eligibility(
        order_facts,
        membership_facts,
        refund_history,
        as_of=as_of,
    )

    return {
        "order_facts": order_facts,
        "membership_facts": membership_facts,
        "refund_history": refund_history,
        "eligibility": eligibility,
    }


def _build_read_only_result(
    *,
    decision: RiskDecision,
    question: str,
    facts: dict[str, object] | None = None,
) -> dict[str, object]:
    """Build a read-only response with business facts."""

    facts = facts or {
        "order_facts": None,
        "membership_facts": None,
        "refund_history": None,
        "eligibility": None,
    }
    eligibility = facts.get("eligibility") or {}
    eligibility_decision = eligibility.get("decision")

    if eligibility_decision:
        status = str(eligibility_decision)
        message = str(
            eligibility.get(
                "reason",
                decision.reason,
            ),
        )
    else:
        status = "not_found"
        message = "未找到属于当前用户的订单。"

    return {
        "action": decision.action.value,
        "intent": decision.intent,
        "status": status,
        "message": message,
        "approval_task_id": None,
        "refund_request_id": None,
        "order_number": _extract_order_number(question),
        **facts,
    }


def _build_rejected_result(
    *,
    decision: RiskDecision,
    question: str,
    message: str | None = None,
) -> dict[str, object]:
    """Build a safe response that performs no business side effect."""

    return {
        "action": RiskAction.REJECT_DIRECT_EXECUTION.value,
        "intent": decision.intent,
        "status": "rejected",
        "message": message or decision.reason,
        "approval_task_id": None,
        "refund_request_id": None,
        "order_number": _extract_order_number(question),
        "order_facts": None,
        "membership_facts": None,
        "refund_history": None,
        "eligibility": None,
    }


def _build_refund_request_result(
    *,
    decision: RiskDecision,
    question: str,
    result: dict[str, object],
) -> dict[str, object]:
    """Convert refund-service output into the common action response."""

    created = bool(result.get("created", False))
    return {
        "action": decision.action.value,
        "intent": decision.intent,
        "status": "pending" if created else str(
            result.get("decision", "rejected"),
        ),
        "message": str(
            result.get(
                "reason",
                "退款申请未创建。" if not created else "退款申请已创建。",
            ),
        ),
        "approval_task_id": None,
        "refund_request_id": result.get("refund_request_id"),
        "order_number": result.get(
            "order_number",
            _extract_order_number(question),
        ),
        "order_facts": None,
        "membership_facts": None,
        "refund_history": None,
        "eligibility": None,
    }


def execute_business_action(
    db: Session,
    *,
    question: str,
    user_id: UUID,
    trace_id: UUID,
    as_of: datetime | None = None,
) -> dict[str, object]:
    """Route one user request through the deterministic risk gate."""

    decision = classify_risk_action(question)
    normalized_as_of = as_of or datetime.now(UTC)

    if decision.action == RiskAction.READ_ONLY:
        order_number = _extract_order_number(question)
        if order_number is None:
            return _build_read_only_result(
                decision=decision,
                question=question,
            )

        owned_order = _find_owned_order(
            db,
            order_number=order_number,
            user_id=user_id,
        )
        if owned_order is None:
            return _build_read_only_result(
                decision=decision,
                question=question,
            )

        order, membership = owned_order
        facts = _build_business_facts(
            db,
            order=order,
            membership=membership,
            as_of=normalized_as_of,
        )
        return _build_read_only_result(
            decision=decision,
            question=question,
            facts=facts,
        )

    if decision.action == RiskAction.REJECT_DIRECT_EXECUTION:
        return _build_rejected_result(
            decision=decision,
            question=question,
        )

    if decision.action == RiskAction.CREATE_REFUND_REQUEST:
        order_number = _extract_order_number(question)
        if order_number is None:
            return _build_rejected_result(
                decision=decision,
                question=question,
                message=(
                    "退款申请必须包含有效订单号，"
                    "系统不会创建不明确的退款申请。"
                ),
            )

        refund_result = create_refund_request(
            db,
            order_number=order_number,
            user_id=user_id,
            reason=question,
            trace_id=trace_id,
            as_of=normalized_as_of,
        )
        return _build_refund_request_result(
            decision=decision,
            question=question,
            result=refund_result,
        )

    if decision.action != RiskAction.CREATE_APPROVAL_TASK:
        raise ValueError(
            f"Unsupported risk action: {decision.action}"
        )

    order_number = _extract_order_number(question)
    task_type = _select_high_risk_task_type(question)

    if task_type == ApprovalTaskType.DIRECT_REFUND:
        if order_number is None:
            return _build_rejected_result(
                decision=decision,
                question=question,
                message=(
                    "直接退款请求必须包含有效的订单号，"
                    "系统不会执行不明确的退款操作。"
                ),
            )

        owned_order = _find_owned_order(
            db,
            order_number=order_number,
            user_id=user_id,
        )
        if owned_order is None:
            return _build_rejected_result(
                decision=decision,
                question=question,
                message=(
                    f"未找到属于当前用户的订单 {order_number}，"
                    "系统不会为未知订单创建退款审批任务。"
                ),
            )

        resource_type = "order"
        resource_id = owned_order[0].id
        reason = (
            f"用户请求直接退款订单 {order_number}，"
            "该操作必须经过人工审批。"
        )
    elif task_type == ApprovalTaskType.MODIFY_POLICY:
        resource_type = "policy"
        resource_id = None
        reason = (
            "用户请求修改退款政策或退款规则，"
            "该操作必须经过人工审批。"
        )
    elif task_type == ApprovalTaskType.DELETE_DOCUMENT:
        resource_type = "document"
        resource_id = None
        reason = (
            "用户请求删除政策文档，"
            "该操作必须经过人工审批。"
        )
    else:
        raise ValueError(
            f"Unsupported high-risk task type: {task_type}"
        )

    approval_task = create_approval_task(
        db,
        task_type=task_type,
        resource_type=resource_type,
        resource_id=resource_id,
        requested_by=user_id,
        trace_id=trace_id,
        reason=reason,
        metadata={
            "question": question,
            "order_number": order_number,
        },
    )

    return {
        "action": decision.action.value,
        "intent": decision.intent,
        "status": "pending",
        "message": (
            "高风险操作不会被系统直接执行，"
            "已创建人工审批任务。"
        ),
        "approval_task_id": approval_task.id,
        "refund_request_id": None,
        "order_number": order_number,
        "order_facts": None,
        "membership_facts": None,
        "refund_history": None,
        "eligibility": None,
    }
