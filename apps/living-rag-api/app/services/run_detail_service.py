from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.agent_node_run import AgentNodeRun
from app.models.agent_run import AgentRun
from app.models.approval_task import ApprovalTask
from app.models.audit_log import AuditLog
from app.models.chat_message import ChatMessage
from app.models.tool_call import ToolCall


class RunNotFoundError(ValueError):
    """Raised when a trace_id is not found in the AgentRun."""


def get_run_detail(
    db: Session,
    trace_id: UUID,
) -> dict[str, object]:
    """Get the details of a run, including its nodes, tool calls, messages, and approval tasks and audit logs.

    Args:
        db (Session): The SQLAlchemy session to use for database access.
        trace_id (UUID): The trace ID of the run to retrieve.

    Returns:
        dict[str, object]: A dictionary containing the run details.

    Raises:
        RunNotFoundError: If the run with the given trace_id is not found.
    """
    # Fetch the AgentRun
    agent_run = db.scalar(
        select(AgentRun).where(AgentRun.trace_id == trace_id)
    )
    if agent_run is None:
        raise RunNotFoundError(f"Run with trace_id {trace_id} not found.")

    # Fetch related AgentNodeRuns
    node_runs = (
        select(AgentNodeRun)
        .where(AgentNodeRun.agent_run_id == agent_run.id)
        .order_by(AgentNodeRun.sequence_number.asc())
    )
    node_runs = db.scalars(node_runs).all()

    # Fetch related ToolCalls
    tool_calls = (
        select(ToolCall)
        .where(ToolCall.agent_run_id == agent_run.id)
        .order_by(ToolCall.created_at.asc())
    )
    tool_calls = db.scalars(tool_calls).all()

    # Fetch related ChatMessages
    chat_messages = (
        select(ChatMessage)
        .where(ChatMessage.trace_id == trace_id)
        .order_by(ChatMessage.created_at.asc())
    )
    chat_messages = db.scalars(chat_messages).all()

    # Fetch related ApprovalTasks
    approval_tasks = (
        select(ApprovalTask)
        .where(ApprovalTask.trace_id == trace_id)
        .order_by(ApprovalTask.created_at.asc())
    )
    approval_tasks = db.scalars(approval_tasks).all()

    # Fetch related AuditLogs
    audit_logs = (
        select(AuditLog)
        .where(AuditLog.trace_id == trace_id)
        .order_by(AuditLog.created_at.asc())
    )
    audit_logs = db.scalars(audit_logs).all()

    return {
        "trace_id": trace_id,
        "agent_run": agent_run,
        "nodes": node_runs,
        "tool_calls": tool_calls,
        "messages": chat_messages,
        "approval_tasks": approval_tasks,
        "audit_logs": audit_logs,
    }
