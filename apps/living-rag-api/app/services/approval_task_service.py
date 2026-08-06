"""Business service for human approval tasks."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.approval_task import (
    ApprovalDecision,
    ApprovalTask,
    ApprovalTaskStatus,
    ApprovalTaskType,
)
from app.models.audit_log import (
    AuditActorType,
    AuditLog,
    AuditResult,
)
from app.models.refund_request import (
    RefundRequest,
    RefundRequestStatus,
)


def create_approval_task(
    db: Session,
    *,
    task_type: ApprovalTaskType,
    resource_type: str,
    resource_id: UUID | None,
    requested_by: UUID | None,
    trace_id: UUID | None,
    reason: str,
    refund_request_id: UUID | None = None,
    metadata: dict[str, object] | None = None,
) -> ApprovalTask:
    """Create a pending approval task and its audit log."""

    normalized_reason = reason.strip()

    if not normalized_reason:
        raise ValueError(
            "Approval task reason cannot be empty."
        )

    normalized_resource_type = resource_type.strip()

    if not normalized_resource_type:
        raise ValueError(
            "Approval task resource type cannot be empty."
        )

    task = ApprovalTask(
        task_type=task_type,
        status=ApprovalTaskStatus.PENDING,
        refund_request_id=refund_request_id,
        resource_type=normalized_resource_type,
        resource_id=resource_id,
        requested_by=requested_by,
        trace_id=trace_id,
        reason=normalized_reason,
        metadata_=metadata or {},
    )

    db.add(task)
    db.flush()

    audit_log = AuditLog(
        actor_type=AuditActorType.AGENT,
        actor_id=requested_by,
        action="create_approval_task",
        resource_type="approval_task",
        resource_id=task.id,
        result=AuditResult.PENDING,
        reason=normalized_reason,
        before_snapshot={},
        after_snapshot={
            "task_type": task.task_type.value,
            "status": task.status.value,
            "resource_type": task.resource_type,
            "resource_id": (
                str(task.resource_id)
                if task.resource_id is not None
                else None
            ),
        },
        trace_id=trace_id,
        metadata_={
            "refund_request_id": (
                str(refund_request_id)
                if refund_request_id is not None
                else None
            ),
        },
    )

    db.add(audit_log)
    db.flush()

    return task


def list_pending_approval_tasks(
    db: Session,
    *,
    task_type: ApprovalTaskType | None = None,
) -> list[ApprovalTask]:
    """Return pending approval tasks ordered from oldest to newest."""

    statement = select(ApprovalTask).where(
        ApprovalTask.status == ApprovalTaskStatus.PENDING.value,
    )

    if task_type is not None:
        statement = statement.where(
            ApprovalTask.task_type == task_type.value,
        )

    statement = statement.order_by(
        ApprovalTask.created_at.asc(),
    )

    return list(db.scalars(statement).all())


def decide_approval_task(
    db: Session,
    *,
    task_id: UUID,
    decision: ApprovalDecision,
    decision_reason: str,
    decided_by: UUID,
) -> ApprovalTask:
    """Approve or reject a pending task and write an audit record."""

    normalized_reason = decision_reason.strip()

    if not normalized_reason:
        raise ValueError(
            "Approval decision reason cannot be empty."
        )

    task_statement = select(ApprovalTask).where(
        ApprovalTask.id == task_id,
    )

    task = db.scalar(task_statement)

    if task is None:
        raise ValueError(
            f"Approval task not found: {task_id}"
        )

    if task.status != ApprovalTaskStatus.PENDING.value:
        raise ValueError(
            "Only pending approval tasks can be decided."
        )

    before_snapshot = {
        "task_type": (
            task.task_type.value
            if isinstance(task.task_type, ApprovalTaskType)
            else task.task_type
        ),
        "status": (
            task.status.value
            if isinstance(task.status, ApprovalTaskStatus)
            else task.status
        ),
        "decision": (
            task.decision.value
            if isinstance(task.decision, ApprovalDecision)
            else task.decision
        ),
    }

    if decision == ApprovalDecision.APPROVE:
        task.status = ApprovalTaskStatus.APPROVED
        audit_result = AuditResult.SUCCESS
        audit_action = "approve_approval_task"

    elif decision == ApprovalDecision.REJECT:
        task.status = ApprovalTaskStatus.REJECTED
        audit_result = AuditResult.DENIED
        audit_action = "reject_approval_task"

    else:
        raise ValueError(
            f"Unsupported approval decision: {decision}"
        )

    task.decision = decision
    task.decision_reason = normalized_reason
    task.decided_by = decided_by
    task.decided_at = datetime.now(UTC)

    if task.refund_request_id is not None:
        refund_statement = select(RefundRequest).where(
            RefundRequest.id == task.refund_request_id,
        )

        refund_request = db.scalar(refund_statement)

        if refund_request is None:
            raise ValueError(
                "Refund request associated with approval task "
                "was not found."
            )

        refund_request.reviewed_at = datetime.now(UTC)

        if decision == ApprovalDecision.APPROVE:
            refund_request.status = RefundRequestStatus.APPROVED

        elif decision == ApprovalDecision.REJECT:
            refund_request.status = RefundRequestStatus.REJECTED
            refund_request.rejection_reason = normalized_reason

    db.flush()

    after_snapshot = {
        "task_type": (
            task.task_type.value
            if isinstance(task.task_type, ApprovalTaskType)
            else task.task_type
        ),
        "status": (
            task.status.value
            if isinstance(task.status, ApprovalTaskStatus)
            else task.status
        ),
        "decision": (
            task.decision.value
            if isinstance(task.decision, ApprovalDecision)
            else task.decision
        ),
        "decided_by": str(task.decided_by),
        "decided_at": task.decided_at.isoformat(),
    }

    audit_log = AuditLog(
        actor_type=AuditActorType.ADMIN,
        actor_id=decided_by,
        action=audit_action,
        resource_type="approval_task",
        resource_id=task.id,
        result=audit_result,
        reason=normalized_reason,
        before_snapshot=before_snapshot,
        after_snapshot=after_snapshot,
        trace_id=task.trace_id,
        metadata_={
            "decision": decision.value,
            "refund_request_id": (
                str(task.refund_request_id)
                if task.refund_request_id is not None
                else None
            ),
        },
    )

    db.add(audit_log)
    db.flush()

    return task