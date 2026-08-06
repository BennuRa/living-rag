"""Persistence helpers for business-action traces."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.agent_run import (
    AgentRun,
    AgentRunStatus,
)
from app.models.chat_message import (
    ChatMessage,
    ChatMessageRole,
    ChatMessageStatus,
)
from app.models.chat_thread import (
    ChatSubject,
    ChatThread,
)
from app.models.user import User


def _subject_for_intent(intent: str) -> ChatSubject:
    """Map a business intent to a conversation subject."""

    subject_by_intent = {
        "policy_qa": ChatSubject.POLICY,
        "order_membership": ChatSubject.ORDER,
        "refund_request": ChatSubject.REFUND,
        "high_risk_operation": ChatSubject.GENERAL,
        "unknown": ChatSubject.GENERAL,
    }

    return subject_by_intent.get(
        intent,
        ChatSubject.GENERAL,
    )


def _stringify_optional_uuid(
    value: object,
) -> str | None:
    """Convert an optional UUID-like value to JSON-safe text."""

    if value is None:
        return None

    return str(value)


def save_business_action_run(
    db: Session,
    *,
    user_id: UUID,
    trace_id: UUID,
    question: str,
    result: dict[str, object],
) -> dict[str, UUID]:
    """Persist one business action and its traceable conversation records."""

    normalized_question = question.strip()

    if not normalized_question:
        raise ValueError(
            "Question must not be blank."
        )

    user = db.scalar(
        select(User).where(
            User.id == user_id,
        ),
    )

    if user is None:
        raise ValueError(
            f"User not found: {user_id}"
        )

    now = datetime.now(UTC)

    intent = str(
        result.get(
            "intent",
            "unknown",
        ),
    )

    action = str(
        result.get(
            "action",
            "reject_direct_execution",
        ),
    )

    status = str(
        result.get(
            "status",
            "rejected",
        ),
    )

    message = str(
        result.get(
            "message",
            "系统未执行该业务操作。",
        ),
    ).strip()

    if not message:
        raise ValueError(
            "Business action message must not be blank."
        )

    thread = ChatThread(
        user_id=user_id,
        title=normalized_question[:255],
        subject=_subject_for_intent(intent),
        last_message_at=now,
        metadata_={
            "source": "business_action",
            "action": action,
            "status": status,
        },
    )

    db.add(thread)
    db.flush()

    user_message = ChatMessage(
        thread_id=thread.id,
        sequence_number=1,
        role=ChatMessageRole.USER,
        content=normalized_question,
        status=ChatMessageStatus.COMPLETED,
        trace_id=trace_id,
        citations=[],
        metadata_={
            "source": "business_action",
        },
    )

    db.add(user_message)
    db.flush()

    assistant_message = ChatMessage(
        thread_id=thread.id,
        sequence_number=2,
        role=ChatMessageRole.ASSISTANT,
        content=message,
        status=ChatMessageStatus.COMPLETED,
        trace_id=trace_id,
        citations=[],
        metadata_={
            "source": "business_action",
            "action": action,
            "status": status,
            "approval_task_id": _stringify_optional_uuid(
                result.get("approval_task_id"),
            ),
            "refund_request_id": _stringify_optional_uuid(
                result.get("refund_request_id"),
            ),
            "order_number": result.get("order_number"),
        },
    )

    db.add(assistant_message)
    db.flush()

    agent_run = AgentRun(
        thread_id=thread.id,
        message_id=assistant_message.id,
        trace_id=trace_id,
        status=AgentRunStatus.SUCCEEDED,
        intent=intent,
        workflow_version="0.1.0",
        model_name="deterministic-business-action",
        prompt_version="v1",
        started_at=now,
        completed_at=now,
        duration_ms=0,
        metadata_={
            "source": "business_action",
            "action": action,
            "status": status,
            "approval_task_id": _stringify_optional_uuid(
                result.get("approval_task_id"),
            ),
            "refund_request_id": _stringify_optional_uuid(
                result.get("refund_request_id"),
            ),
            "order_number": result.get("order_number"),
        },
    )

    db.add(agent_run)
    db.flush()

    return {
        "thread_id": thread.id,
        "user_message_id": user_message.id,
        "assistant_message_id": assistant_message.id,
        "agent_run_id": agent_run.id,
        "trace_id": trace_id,
    }