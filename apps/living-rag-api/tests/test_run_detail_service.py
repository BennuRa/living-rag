"""Tests for the Living RAG run-detail service."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from app.models.agent_node_run import (
    AgentNodeRun,
    AgentNodeRunStatus,
)
from app.models.agent_run import (
    AgentRun,
    AgentRunStatus,
)
from app.models.approval_task import (
    ApprovalTask,
    ApprovalTaskStatus,
    ApprovalTaskType,
)
from app.models.audit_log import (
    AuditActorType,
    AuditLog,
    AuditResult,
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
from app.models.tool_call import (
    ToolCall,
    ToolCallStatus,
)
from app.models.user import (
    User,
    UserStatus,
)
from app.services.run_detail_service import (
    RunNotFoundError,
    get_run_detail,
)


def create_run_owner(
    db_session: Session,
) -> tuple[User, ChatThread]:
    """Create the minimum records required by AgentRun foreign keys."""

    user = User(
        external_id=f"run-detail-test-{uuid4()}",
        email=f"run-detail-{uuid4()}@example.com",
        display_name="Run Detail Test User",
        status=UserStatus.ACTIVE,
    )
    db_session.add(user)
    db_session.flush()

    thread = ChatThread(
        user_id=user.id,
        title="Run detail test thread",
        subject=ChatSubject.GENERAL,
    )
    db_session.add(thread)
    db_session.flush()

    return user, thread


def create_agent_run(
    db_session: Session,
    thread: ChatThread,
    *,
    trace_id,
    status: AgentRunStatus = AgentRunStatus.SUCCEEDED,
    error_code: str | None = None,
    error_message: str | None = None,
) -> AgentRun:
    """Create one AgentRun for run-detail service tests."""

    agent_run = AgentRun(
        thread_id=thread.id,
        trace_id=trace_id,
        status=status,
        intent="policy_qa",
        workflow_version="0.1.0",
        model_name="mock-llm",
        prompt_version="v1",
        started_at=datetime(
            2026,
            1,
            1,
            10,
            0,
            tzinfo=UTC,
        ),
        completed_at=datetime(
            2026,
            1,
            1,
            10,
            0,
            1,
            tzinfo=UTC,
        ),
        duration_ms=1000,
        input_tokens=120,
        output_tokens=80,
        estimated_cost="0.002500",
        error_code=error_code,
        error_message=error_message,
    )
    db_session.add(agent_run)
    db_session.flush()

    return agent_run


def test_get_run_detail_raises_when_trace_id_is_missing(
    db_session: Session,
) -> None:
    """An unknown trace_id must raise a service-layer not-found error."""

    trace_id = uuid4()

    with pytest.raises(
        RunNotFoundError,
        match=str(trace_id),
    ):
        get_run_detail(
            db=db_session,
            trace_id=trace_id,
        )


def test_get_run_detail_returns_empty_related_lists(
    db_session: Session,
) -> None:
    """A valid run without related records returns empty collections."""

    _, thread = create_run_owner(db_session)
    trace_id = uuid4()
    agent_run = create_agent_run(
        db_session,
        thread,
        trace_id=trace_id,
    )

    detail = get_run_detail(
        db=db_session,
        trace_id=trace_id,
    )

    assert detail["trace_id"] == trace_id
    assert detail["agent_run"] is agent_run
    assert detail["agent_run"].trace_id == trace_id
    assert detail["nodes"] == []
    assert detail["tool_calls"] == []
    assert detail["messages"] == []
    assert detail["approval_tasks"] == []
    assert detail["audit_logs"] == []


def test_get_run_detail_returns_complete_trace_details(
    db_session: Session,
) -> None:
    """A complete Agent run returns all Trace-related records."""

    user, thread = create_run_owner(db_session)
    trace_id = uuid4()
    agent_run = create_agent_run(
        db_session,
        thread,
        trace_id=trace_id,
    )

    first_node = AgentNodeRun(
        agent_run_id=agent_run.id,
        node_name="classify_intent",
        sequence_number=1,
        status=AgentNodeRunStatus.SUCCEEDED,
        input_snapshot={
            "question": "当前退款政策是多少天？",
        },
        output_snapshot={
            "intent": "policy_qa",
        },
        duration_ms=10,
    )
    second_node = AgentNodeRun(
        agent_run_id=agent_run.id,
        node_name="retrieve_documents",
        sequence_number=2,
        status=AgentNodeRunStatus.SUCCEEDED,
        input_snapshot={
            "intent": "policy_qa",
        },
        output_snapshot={
            "result_count": 2,
        },
        duration_ms=25,
    )
    db_session.add_all([second_node, first_node])
    db_session.flush()

    base_time = datetime(
        2026,
        1,
        1,
        10,
        0,
        2,
        tzinfo=UTC,
    )

    tool_call = ToolCall(
        agent_run_id=agent_run.id,
        node_run_id=second_node.id,
        tool_name="search_documents",
        status=ToolCallStatus.SUCCEEDED,
        arguments={
            "query": "当前退款政策",
        },
        result={
            "count": 2,
        },
        started_at=base_time,
        completed_at=base_time + timedelta(milliseconds=15),
        duration_ms=15,
    )
    db_session.add(tool_call)

    user_message = ChatMessage(
        thread_id=thread.id,
        sequence_number=1,
        role=ChatMessageRole.USER,
        content="当前退款政策是多少天？",
        status=ChatMessageStatus.COMPLETED,
        trace_id=trace_id,
        created_at=base_time + timedelta(seconds=1),
    )
    assistant_message = ChatMessage(
        thread_id=thread.id,
        sequence_number=2,
        role=ChatMessageRole.ASSISTANT,
        content="当前有效退款政策为签收后 15 天。",
        status=ChatMessageStatus.COMPLETED,
        trace_id=trace_id,
        citations=[
            {
                "chunk_id": str(uuid4()),
                "document_version": "v3",
            },
        ],
        created_at=base_time + timedelta(seconds=2),
    )
    db_session.add_all([assistant_message, user_message])

    approval_task = ApprovalTask(
        task_type=ApprovalTaskType.DIRECT_REFUND,
        status=ApprovalTaskStatus.PENDING,
        resource_type="refund_request",
        resource_id=None,
        requested_by=user.id,
        trace_id=trace_id,
        reason="Direct refund requires human approval.",
        created_at=base_time + timedelta(seconds=3),
    )
    db_session.add(approval_task)

    audit_log = AuditLog(
        actor_type=AuditActorType.AGENT,
        actor_id=None,
        action="create_approval_task",
        resource_type="approval_task",
        resource_id=approval_task.id,
        result=AuditResult.PENDING,
        reason="A high-risk refund action requires approval.",
        trace_id=trace_id,
        created_at=base_time + timedelta(seconds=4),
    )
    db_session.add(audit_log)
    db_session.flush()

    detail = get_run_detail(
        db=db_session,
        trace_id=trace_id,
    )

    assert detail["trace_id"] == trace_id
    assert detail["agent_run"] is agent_run

    nodes = detail["nodes"]
    assert [node.node_name for node in nodes] == [
        "classify_intent",
        "retrieve_documents",
    ]
    assert [node.sequence_number for node in nodes] == [1, 2]

    tool_calls = detail["tool_calls"]
    assert len(tool_calls) == 1
    assert tool_calls[0].tool_name == "search_documents"
    assert tool_calls[0].agent_run_id == agent_run.id
    assert tool_calls[0].node_run_id == second_node.id

    messages = detail["messages"]
    assert [message.sequence_number for message in messages] == [1, 2]
    assert messages[0].role == ChatMessageRole.USER
    assert messages[1].role == ChatMessageRole.ASSISTANT
    assert all(message.trace_id == trace_id for message in messages)

    approval_tasks = detail["approval_tasks"]
    assert len(approval_tasks) == 1
    assert approval_tasks[0].trace_id == trace_id
    assert approval_tasks[0].task_type == ApprovalTaskType.DIRECT_REFUND

    audit_logs = detail["audit_logs"]
    assert len(audit_logs) == 1
    assert audit_logs[0].trace_id == trace_id
    assert audit_logs[0].action == "create_approval_task"


def test_get_run_detail_returns_failed_run_error_fields(
    db_session: Session,
) -> None:
    """A failed AgentRun keeps its failure information in the detail."""

    _, thread = create_run_owner(db_session)
    trace_id = uuid4()
    agent_run = create_agent_run(
        db_session,
        thread,
        trace_id=trace_id,
        status=AgentRunStatus.FAILED,
        error_code="citation_validation_failed",
        error_message="The generated citation does not match a stored chunk.",
    )

    detail = get_run_detail(
        db=db_session,
        trace_id=trace_id,
    )

    returned_run = detail["agent_run"]

    assert returned_run is agent_run
    assert returned_run.status == AgentRunStatus.FAILED
    assert returned_run.error_code == "citation_validation_failed"
    assert (
        returned_run.error_message
        == "The generated citation does not match a stored chunk."
    )