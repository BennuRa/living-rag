from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.approval_task import (
    ApprovalDecision,
    ApprovalTask,
    ApprovalTaskStatus,
    ApprovalTaskType,
)
from app.models.audit_log import (
    AuditLog,
    AuditResult,
)
from app.models.membership_account import (
    MembershipAccount,
    MembershipTier,
)
from app.models.order import Order, OrderStatus
from app.models.refund_request import (
    RefundRequest,
    RefundRequestStatus,
)
from app.models.user import User
from app.services.approval_task_service import (
    create_approval_task,
    decide_approval_task,
    list_pending_approval_tasks,
)


def _create_user(
    db_session: Session,
    *,
    external_id: str,
    display_name: str,
) -> User:
    """Create one isolated test user."""

    user = User(
        external_id=external_id,
        display_name=display_name,
    )

    db_session.add(user)
    db_session.flush()

    return user


def _create_refund_request(
    db_session: Session,
    *,
    user_external_id: str,
    order_number: str,
    request_number: str,
) -> RefundRequest:
    """Create an order and refund request for approval tests."""

    user = User(
        external_id=user_external_id,
        display_name="Refund Test User",
    )

    membership = MembershipAccount(
        user=user,
        membership_number=f"M-{user_external_id}",
        tier=MembershipTier.STANDARD,
    )

    order = Order(
        membership_account=membership,
        order_number=order_number,
        status=OrderStatus.COMPLETED,
        total_amount=Decimal("199.00"),
        metadata_={
            "received_at": "2026-01-05T14:30:00+08:00",
            "returnable": True,
            "product_name": "Test Product",
        },
    )

    refund_request = RefundRequest(
        order=order,
        request_number=request_number,
        status=RefundRequestStatus.PENDING,
        requested_amount=Decimal("199.00"),
        reason="User requested a direct refund.",
    )

    db_session.add(user)
    db_session.flush()

    return refund_request


def test_create_approval_task_writes_pending_audit_log(
    db_session: Session,
) -> None:
    """Creating an approval task should write a pending audit record."""

    user = _create_user(
        db_session,
        external_id="USR-APPROVAL-001",
        display_name="Approval Request User",
    )

    trace_id = uuid4()

    task = create_approval_task(
        db_session,
        task_type=ApprovalTaskType.DIRECT_REFUND,
        resource_type="order",
        resource_id=uuid4(),
        requested_by=user.id,
        trace_id=trace_id,
        reason="User requested a direct refund.",
    )

    assert task.id is not None
    assert task.task_type == ApprovalTaskType.DIRECT_REFUND
    assert task.status == ApprovalTaskStatus.PENDING
    assert task.reason == "User requested a direct refund."
    assert task.trace_id == trace_id
    assert task.metadata_ == {}

    audit_statement = select(AuditLog).where(
        AuditLog.resource_id == task.id,
        AuditLog.action == "create_approval_task",
    )

    audit_log = db_session.scalar(audit_statement)

    assert audit_log is not None
    assert audit_log.result == AuditResult.PENDING
    assert audit_log.trace_id == trace_id
    assert audit_log.after_snapshot["status"] == "pending"


def test_list_pending_approval_tasks_filters_by_type(
    db_session: Session,
) -> None:
    """Pending task listing should support task-type filtering."""

    user = _create_user(
        db_session,
        external_id="USR-APPROVAL-002",
        display_name="Approval List User",
    )

    create_approval_task(
        db_session,
        task_type=ApprovalTaskType.DIRECT_REFUND,
        resource_type="order",
        resource_id=uuid4(),
        requested_by=user.id,
        trace_id=uuid4(),
        reason="Direct refund request.",
    )

    create_approval_task(
        db_session,
        task_type=ApprovalTaskType.MODIFY_POLICY,
        resource_type="document_version",
        resource_id=uuid4(),
        requested_by=user.id,
        trace_id=uuid4(),
        reason="Policy modification request.",
    )

    all_pending = list_pending_approval_tasks(db_session)
    direct_refund_tasks = list_pending_approval_tasks(
        db_session,
        task_type=ApprovalTaskType.DIRECT_REFUND,
    )

    assert len(all_pending) == 2
    assert len(direct_refund_tasks) == 1
    assert (
        direct_refund_tasks[0].task_type
        == ApprovalTaskType.DIRECT_REFUND
    )


def test_approve_task_updates_refund_request_and_audit_log(
    db_session: Session,
) -> None:
    """Approval should update both the task and its refund request."""

    refund_request = _create_refund_request(
        db_session,
        user_external_id="USR-APPROVAL-003",
        order_number="O-APPROVAL-001",
        request_number="R-APPROVAL-001",
    )

    admin = _create_user(
        db_session,
        external_id="ADMIN-APPROVAL-001",
        display_name="Approval Admin",
    )

    task = create_approval_task(
        db_session,
        task_type=ApprovalTaskType.DIRECT_REFUND,
        resource_type="refund_request",
        resource_id=refund_request.id,
        refund_request_id=refund_request.id,
        requested_by=None,
        trace_id=uuid4(),
        reason="User requested immediate refund.",
    )

    decided_task = decide_approval_task(
        db_session,
        task_id=task.id,
        decision=ApprovalDecision.APPROVE,
        decision_reason="Refund request passed human review.",
        decided_by=admin.id,
    )

    assert decided_task.status == ApprovalTaskStatus.APPROVED
    assert decided_task.decision == ApprovalDecision.APPROVE
    assert decided_task.decided_by == admin.id
    assert decided_task.decided_at is not None

    db_session.refresh(refund_request)

    assert refund_request.status == RefundRequestStatus.APPROVED
    assert refund_request.reviewed_at is not None

    audit_statement = select(AuditLog).where(
        AuditLog.resource_id == task.id,
        AuditLog.action == "approve_approval_task",
    )

    audit_log = db_session.scalar(audit_statement)

    assert audit_log is not None
    assert audit_log.result == AuditResult.SUCCESS
    assert audit_log.actor_id == admin.id
    assert audit_log.after_snapshot["status"] == "approved"
    assert audit_log.after_snapshot["decision"] == "approve"


def test_reject_task_updates_refund_request_and_audit_log(
    db_session: Session,
) -> None:
    """Rejection should update the refund request with the rejection reason."""

    refund_request = _create_refund_request(
        db_session,
        user_external_id="USR-APPROVAL-004",
        order_number="O-APPROVAL-002",
        request_number="R-APPROVAL-002",
    )

    admin = _create_user(
        db_session,
        external_id="ADMIN-APPROVAL-002",
        display_name="Reject Admin",
    )

    task = create_approval_task(
        db_session,
        task_type=ApprovalTaskType.REFUND_REQUEST,
        resource_type="refund_request",
        resource_id=refund_request.id,
        refund_request_id=refund_request.id,
        requested_by=None,
        trace_id=uuid4(),
        reason="User submitted a refund request.",
    )

    decided_task = decide_approval_task(
        db_session,
        task_id=task.id,
        decision=ApprovalDecision.REJECT,
        decision_reason="The request does not satisfy the policy.",
        decided_by=admin.id,
    )

    assert decided_task.status == ApprovalTaskStatus.REJECTED
    assert decided_task.decision == ApprovalDecision.REJECT
    assert decided_task.decision_reason == (
        "The request does not satisfy the policy."
    )

    db_session.refresh(refund_request)

    assert refund_request.status == RefundRequestStatus.REJECTED
    assert refund_request.rejection_reason == (
        "The request does not satisfy the policy."
    )
    assert refund_request.reviewed_at is not None

    audit_statement = select(AuditLog).where(
        AuditLog.resource_id == task.id,
        AuditLog.action == "reject_approval_task",
    )

    audit_log = db_session.scalar(audit_statement)

    assert audit_log is not None
    assert audit_log.result == AuditResult.DENIED
    assert audit_log.actor_id == admin.id
    assert audit_log.after_snapshot["status"] == "rejected"
    assert audit_log.after_snapshot["decision"] == "reject"


def test_deciding_non_pending_task_is_rejected(
    db_session: Session,
) -> None:
    """An approved task must not be approved or rejected again."""

    user = _create_user(
        db_session,
        external_id="USR-APPROVAL-005",
        display_name="Duplicate Decision User",
    )

    admin = _create_user(
        db_session,
        external_id="ADMIN-APPROVAL-003",
        display_name="Duplicate Decision Admin",
    )

    task = create_approval_task(
        db_session,
        task_type=ApprovalTaskType.DIRECT_REFUND,
        resource_type="order",
        resource_id=uuid4(),
        requested_by=user.id,
        trace_id=uuid4(),
        reason="Direct refund request.",
    )

    decide_approval_task(
        db_session,
        task_id=task.id,
        decision=ApprovalDecision.APPROVE,
        decision_reason="Approved once.",
        decided_by=admin.id,
    )

    with pytest.raises(
        ValueError,
        match="Only pending approval tasks can be decided.",
    ):
        decide_approval_task(
            db_session,
            task_id=task.id,
            decision=ApprovalDecision.REJECT,
            decision_reason="Attempted duplicate decision.",
            decided_by=admin.id,
        )


def test_empty_reason_is_rejected_when_creating_task(
    db_session: Session,
) -> None:
    """An approval task cannot be created without a meaningful reason."""

    user = _create_user(
        db_session,
        external_id="USR-APPROVAL-006",
        display_name="Empty Reason User",
    )

    with pytest.raises(
        ValueError,
        match="Approval task reason cannot be empty.",
    ):
        create_approval_task(
            db_session,
            task_type=ApprovalTaskType.DIRECT_REFUND,
            resource_type="order",
            resource_id=uuid4(),
            requested_by=user.id,
            trace_id=uuid4(),
            reason="   ",
        )


def test_empty_decision_reason_is_rejected(
    db_session: Session,
) -> None:
    """An approval decision must include a reason."""

    user = _create_user(
        db_session,
        external_id="USR-APPROVAL-007",
        display_name="Empty Decision Reason User",
    )

    admin = _create_user(
        db_session,
        external_id="ADMIN-APPROVAL-004",
        display_name="Empty Decision Reason Admin",
    )

    task = create_approval_task(
        db_session,
        task_type=ApprovalTaskType.DELETE_DOCUMENT,
        resource_type="document_version",
        resource_id=uuid4(),
        requested_by=user.id,
        trace_id=uuid4(),
        reason="Delete document request.",
    )

    with pytest.raises(
        ValueError,
        match="Approval decision reason cannot be empty.",
    ):
        decide_approval_task(
            db_session,
            task_id=task.id,
            decision=ApprovalDecision.APPROVE,
            decision_reason=" ",
            decided_by=admin.id,
        )


def test_pending_list_excludes_decided_tasks(
    db_session: Session,
) -> None:
    """The pending list must exclude already decided tasks."""

    user = _create_user(
        db_session,
        external_id="USR-APPROVAL-008",
        display_name="Pending List User",
    )

    admin = _create_user(
        db_session,
        external_id="ADMIN-APPROVAL-005",
        display_name="Pending List Admin",
    )

    pending_task = create_approval_task(
        db_session,
        task_type=ApprovalTaskType.DIRECT_REFUND,
        resource_type="order",
        resource_id=uuid4(),
        requested_by=user.id,
        trace_id=uuid4(),
        reason="Pending direct refund request.",
    )

    approved_task = create_approval_task(
        db_session,
        task_type=ApprovalTaskType.DIRECT_REFUND,
        resource_type="order",
        resource_id=uuid4(),
        requested_by=user.id,
        trace_id=uuid4(),
        reason="Approved direct refund request.",
    )

    decide_approval_task(
        db_session,
        task_id=approved_task.id,
        decision=ApprovalDecision.APPROVE,
        decision_reason="Approved after review.",
        decided_by=admin.id,
    )

    pending_tasks = list_pending_approval_tasks(db_session)

    assert len(pending_tasks) == 1
    assert pending_tasks[0].id == pending_task.id