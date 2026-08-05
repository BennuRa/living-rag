"""Persistence helpers for Living RAG question-answering runs."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TypedDict
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.agent_node_run import (
    AgentNodeRun,
    AgentNodeRunStatus,
)
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
from app.services.qa_state import LivingRAGState


class NodeSnapshot(TypedDict, total=False):
    """Serializable summary of one LangGraph node execution."""

    node_name: str
    sequence_number: int
    status: str
    input_snapshot: dict[str, object]
    output_snapshot: dict[str, object]
    started_at: datetime
    completed_at: datetime
    duration_ms: int


def save_qa_run(
    db: Session,
    state: LivingRAGState,
    *,
    user_id: UUID,
    trace_id: UUID,
    node_snapshots: list[NodeSnapshot] | None = None,
) -> dict[str, UUID]:
    """Persist one completed QA run and its chat and node records."""

    question = state.get("question", "").strip()

    if not question:
        raise ValueError("Question must not be blank.")

    try:
        user = db.scalar(
            select(User).where(User.id == user_id),
        )

        if user is None:
            raise ValueError(f"User not found: {user_id}")

        now = datetime.now(UTC)
        intent = state.get("intent", "unknown")

        subject_by_intent = {
            "policy_qa": ChatSubject.POLICY,
            "order_membership": ChatSubject.ORDER,
            "refund_request": ChatSubject.REFUND,
            "high_risk_operation": ChatSubject.GENERAL,
            "unknown": ChatSubject.GENERAL,
        }

        thread = ChatThread(
            user_id=user_id,
            title=question[:255],
            subject=subject_by_intent.get(
                intent,
                ChatSubject.GENERAL,
            ),
            last_message_at=now,
        )
        db.add(thread)
        db.flush()

        user_message = ChatMessage(
            thread_id=thread.id,
            sequence_number=1,
            role=ChatMessageRole.USER,
            content=question,
            status=ChatMessageStatus.COMPLETED,
            trace_id=trace_id,
        )
        db.add(user_message)
        db.flush()

        citations = [
            citation.model_dump(mode="json")
            for citation in state.get("citations", [])
        ]

        answer = state.get(
            "answer",
            "I do not have enough grounded evidence to answer this question.",
        ).strip()

        if not answer:
            raise ValueError("Answer must not be blank.")

        assistant_message = ChatMessage(
            thread_id=thread.id,
            sequence_number=2,
            role=ChatMessageRole.ASSISTANT,
            content=answer,
            status=ChatMessageStatus.COMPLETED,
            trace_id=trace_id,
            citations=citations,
            metadata_={
                "conditions": state.get("conditions", []),
                "confidence": state.get("confidence", 0.0),
                "limitations": state.get("limitations", []),
                "citation_valid": state.get("citation_valid", False),
                "conflict_summaries": state.get(
                    "conflict_summaries",
                    [],
                ),
                "conflict_blocking": state.get(
                    "conflict_blocking",
                    False,
                ),
                "conflict_notice": state.get(
                    "conflict_notice",
                    "",
                ),
            },
        )
        db.add(assistant_message)
        db.flush()

        completed_at = datetime.now(UTC)

        agent_run = AgentRun(
            thread_id=thread.id,
            message_id=assistant_message.id,
            trace_id=trace_id,
            status=AgentRunStatus.SUCCEEDED,
            intent=intent,
            workflow_version="0.1.0",
            model_name="mock-llm",
            prompt_version="v1",
            started_at=now,
            completed_at=completed_at,
            duration_ms=max(
                0,
                int(
                    (
                        completed_at - now
                    ).total_seconds()
                    * 1000
                ),
            ),
            metadata_={
                "retrieval_count": len(
                    state.get("retrieval_results", []),
                ),
                "graded_count": len(
                    state.get("graded_results", []),
                ),
                "citation_valid": state.get(
                    "citation_valid",
                    False,
                ),
                "confidence": state.get(
                    "confidence",
                    0.0,
                ),
                "conflict_blocking": state.get(
                    "conflict_blocking",
                    False,
                ),
            },
        )
        db.add(agent_run)
        db.flush()

        for default_sequence, snapshot in enumerate(
            node_snapshots or [],
            start=1,
        ):
            node_name = snapshot.get(
                "node_name",
                f"node_{default_sequence}",
            )

            if not node_name.strip():
                raise ValueError("Node name must not be blank.")

            sequence_number = snapshot.get(
                "sequence_number",
                default_sequence,
            )

            if sequence_number <= 0:
                raise ValueError(
                    "Node sequence number must be greater than zero.",
                )

            node_status = AgentNodeRunStatus(
                snapshot.get(
                    "status",
                    AgentNodeRunStatus.SUCCEEDED.value,
                ),
            )

            node_run = AgentNodeRun(
                agent_run_id=agent_run.id,
                node_name=node_name,
                sequence_number=sequence_number,
                status=node_status,
                input_snapshot=snapshot.get(
                    "input_snapshot",
                    {},
                ),
                output_snapshot=snapshot.get(
                    "output_snapshot",
                    {},
                ),
                started_at=snapshot.get(
                    "started_at",
                    now,
                ),
                completed_at=snapshot.get(
                    "completed_at",
                    completed_at,
                ),
                duration_ms=snapshot.get(
                    "duration_ms",
                    0,
                ),
            )
            db.add(node_run)

        db.commit()

        return {
            "thread_id": thread.id,
            "user_message_id": user_message.id,
            "assistant_message_id": assistant_message.id,
            "agent_run_id": agent_run.id,
            "trace_id": trace_id,
        }

    except Exception:
        db.rollback()
        raise
