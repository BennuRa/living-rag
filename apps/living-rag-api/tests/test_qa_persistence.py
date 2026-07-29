"""Tests for Living RAG QA run persistence."""

from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.agent_run import AgentRun
from app.models.chat_message import ChatMessage
from app.models.chat_thread import ChatThread
from app.models.user import User, UserStatus
from app.services.qa_persistence import save_qa_run


def create_test_user(db_session: Session) -> User:
    """Create one user owned by the current rollback-only test."""

    user = User(
        external_id=f"persistence-test-{uuid4()}",
        email="persistence@example.com",
        display_name="Persistence Test User",
        status=UserStatus.ACTIVE,
    )
    db_session.add(user)
    db_session.flush()

    return user


def make_qa_state() -> dict[str, object]:
    """Build a minimal completed QA state for persistence tests."""

    return {
        "question": "退款时限是多少",
        "user_id": str(uuid4()),
        "trace_id": str(uuid4()),
        "intent": "policy_qa",
        "retrieval_results": [],
        "graded_results": [],
        "answer": "退款政策支持有引用的回答。",
        "conditions": [
            "The answer is limited to the retrieved evidence.",
        ],
        "citation_indices": [],
        "citations": [],
        "confidence": 0.85,
        "limitations": [],
        "citation_valid": True,
    }


def test_save_qa_run_persists_thread_messages_and_agent_run(
    db_session: Session,
) -> None:
    """A completed QA state creates the linked conversation and run records."""

    user = create_test_user(db_session)
    trace_id = uuid4()
    state = make_qa_state()

    persisted_ids = save_qa_run(
        db_session,
        state,
        user_id=user.id,
        trace_id=trace_id,
        node_snapshots=[
            {
                "node_name": "classify_intent",
                "sequence_number": 1,
                "status": "succeeded",
                "input_snapshot": {
                    "question": state["question"],
                },
                "output_snapshot": {
                    "intent": "policy_qa",
                },
                "duration_ms": 2,
            },
            {
                "node_name": "generate_answer",
                "sequence_number": 2,
                "status": "succeeded",
                "input_snapshot": {
                    "context": "grounded evidence",
                },
                "output_snapshot": {
                    "answer": state["answer"],
                },
                "duration_ms": 4,
            },
        ],
    )

    thread = db_session.get(
        ChatThread,
        persisted_ids["thread_id"],
    )
    assert thread is not None
    assert thread.user_id == user.id

    messages = db_session.scalars(
        select(ChatMessage)
        .where(ChatMessage.thread_id == thread.id)
        .order_by(ChatMessage.sequence_number),
    ).all()

    assert len(messages) == 2
    assert messages[0].content == "退款时限是多少"
    assert messages[1].content == "退款政策支持有引用的回答。"
    assert messages[0].trace_id == trace_id
    assert messages[1].trace_id == trace_id
    assert messages[1].metadata_["confidence"] == 0.85

    agent_run = db_session.get(
        AgentRun,
        persisted_ids["agent_run_id"],
    )
    assert agent_run is not None
    assert agent_run.trace_id == trace_id
    assert agent_run.thread_id == thread.id
    assert agent_run.message_id == messages[1].id
    assert len(agent_run.node_runs) == 2
    assert agent_run.node_runs[0].node_name == "classify_intent"
    assert agent_run.node_runs[1].node_name == "generate_answer"


def test_save_qa_run_rolls_back_when_node_snapshot_is_invalid(
    db_session: Session,
) -> None:
    """An invalid node snapshot must roll back every previously flushed record."""

    user = create_test_user(db_session)
    state = make_qa_state()

    with pytest.raises(ValueError, match="Node name must not be blank"):
        save_qa_run(
            db_session,
            state,
            user_id=user.id,
            trace_id=uuid4(),
            node_snapshots=[
                {
                    "node_name": "",
                    "sequence_number": 1,
                    "status": "succeeded",
                },
            ],
        )

    thread_count = db_session.scalar(
        select(func.count()).select_from(ChatThread),
    )
    message_count = db_session.scalar(
        select(func.count()).select_from(ChatMessage),
    )
    agent_run_count = db_session.scalar(
        select(func.count()).select_from(AgentRun),
    )

    assert thread_count == 0
    assert message_count == 0
    assert agent_run_count == 0