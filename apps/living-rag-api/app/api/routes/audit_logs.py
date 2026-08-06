"""API routes for querying immutable audit logs."""

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.audit_log import AuditLog
from app.schemas.audit_log import AuditLogResponse


router = APIRouter(
    prefix="/audit-logs",
    tags=["audit-logs"],
)


@router.get(
    "",
    response_model=list[AuditLogResponse],
)
def list_audit_logs(
    resource_type: str | None = Query(
        default=None,
        min_length=1,
        max_length=128,
    ),
    resource_id: UUID | None = None,
    trace_id: UUID | None = None,
    action: str | None = Query(
        default=None,
        min_length=1,
        max_length=128,
    ),
    db: Session = Depends(get_db),
) -> list[AuditLogResponse]:
    """List audit logs with optional trace and resource filters."""

    statement = select(AuditLog).order_by(
        AuditLog.created_at.desc(),
    )

    if resource_type is not None:
        statement = statement.where(
            AuditLog.resource_type == resource_type,
        )

    if resource_id is not None:
        statement = statement.where(
            AuditLog.resource_id == resource_id,
        )

    if trace_id is not None:
        statement = statement.where(
            AuditLog.trace_id == trace_id,
        )

    if action is not None:
        statement = statement.where(
            AuditLog.action == action,
        )

    audit_logs = db.scalars(statement).all()

    return [
        AuditLogResponse.model_validate(audit_log)
        for audit_log in audit_logs
    ]