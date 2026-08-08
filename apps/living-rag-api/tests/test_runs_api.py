"""API tests for complete Living RAG run details."""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.database import get_db
from app.main import app
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


@pytest.fixture
def client(db_session) -> TestClient:
    """Use the isolated database session for run API tests."""

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


def create_run_owner(
    db_session,
) -> tuple[User, ChatThread]:
    """Create the minimum records required by AgentRun."""

    user = User(
        external_id=f"run-api-test-{uuid4()}",
        email=f"run-api-{uuid4()}@example.com",
        display_name="Run API Test User",
        status=UserStatus.ACTIVE,
    )
    db_session.add(user)
    db_session.flush()

    thread = ChatThread(
        user_id=user.id,
        title="Run API test thread",
        subject=ChatSubject.GENERAL,
    )
    db_session.add(thread)
    db_session.flush()

    return user, thread


def create_agent_run(
    db_session,
    thread: ChatThread,
    *,
    trace_id,
) -> AgentRun:
    """Create one successful AgentRun."""

    agent_run = AgentRun(
        thread_id=thread.id,
        trace_id=trace_id,
        status=AgentRunStatus.SUCCEEDED,
        intent="policy_qa",
        workflow_version="0.1.0",
        model_name="mock-llm",
        prompt_version="v1",
        duration_ms=125,
        input_tokens=100,
        output_tokens=60,
        estimated_cost="0.001500",
        metadata_={
            "citation_valid": True,
            "retrieval_count": 2,
        },
    )
    db_session.add(agent_run)
    db_session.flush()

    return agent_run


def create_complete_trace(
    db_session,
) -> dict[str, object]:
    """Create one complete Trace with all related records."""

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
        duration_ms=20,
    )

    db_session.add_all(
        [
            first_node,
            second_node,
        ],
    )
    db_session.flush()

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
        citations=[],
        metadata_={
            "source": "chat",
        },
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
        metadata_={
            "confidence": 0.95,
        },
    )

    db_session.add_all(
        [
            user_message,
            assistant_message,
        ],
    )
    db_session.flush()

    approval_task = ApprovalTask(
        task_type=ApprovalTaskType.DIRECT_REFUND,
        status=ApprovalTaskStatus.PENDING,
        resource_type="refund_request",
        resource_id=None,
        requested_by=user.id,
        trace_id=trace_id,
        reason="Direct refund requires human approval.",
        metadata_={
            "risk_level": "high",
        },
    )
    db_session.add(approval_task)
    db_session.flush()

    audit_log = AuditLog(
        actor_type=AuditActorType.AGENT,
        actor_id=None,
        action="create_approval_task",
        resource_type="approval_task",
        resource_id=approval_task.id,
        result=AuditResult.PENDING,
        reason="A high-risk refund action requires approval.",
        before_snapshot={},
        after_snapshot={
            "approval_task_id": str(approval_task.id),
        },
        trace_id=trace_id,
        metadata_={
            "source": "business_action",
        },
    )
    db_session.add(audit_log)
    db_session.flush()

    return {
        "trace_id": trace_id,
        "agent_run": agent_run,
        "first_node": first_node,
        "second_node": second_node,
        "tool_call": tool_call,
        "user_message": user_message,
        "assistant_message": assistant_message,
        "approval_task": approval_task,
        "audit_log": audit_log,
    }


def test_get_run_detail_returns_complete_trace(
    client: TestClient,
    db_session,
) -> None:
    """The run endpoint returns all records for one complete Trace."""

    trace = create_complete_trace(db_session)
    trace_id = trace["trace_id"]

    response = client.get(
        f"/runs/{trace_id}",
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["trace_id"] == str(trace_id)

    assert payload["agent_run"]["id"] == str(
        trace["agent_run"].id,
    )
    assert payload["agent_run"]["trace_id"] == str(trace_id)
    assert payload["agent_run"]["status"] == "succeeded"
    assert payload["agent_run"]["input_tokens"] == 100
    assert payload["agent_run"]["output_tokens"] == 60
    assert payload["agent_run"]["metadata"] == {
        "citation_valid": True,
        "retrieval_count": 2,
    }

    assert [
        node["node_name"]
        for node in payload["nodes"]
    ] == [
        "classify_intent",
        "retrieve_documents",
    ]
    assert [
        node["sequence_number"]
        for node in payload["nodes"]
    ] == [1, 2]

    assert len(payload["tool_calls"]) == 1
    assert payload["tool_calls"][0]["tool_name"] == (
        "search_documents"
    )
    assert payload["tool_calls"][0]["agent_run_id"] == str(
        trace["agent_run"].id,
    )
    assert payload["tool_calls"][0]["node_run_id"] == str(
        trace["second_node"].id,
    )

    assert len(payload["messages"]) == 2
    assert payload["messages"][0]["role"] == "user"
    assert payload["messages"][1]["role"] == "assistant"
    assert payload["messages"][1]["trace_id"] == str(trace_id)
    assert payload["messages"][1]["citations"][0][
        "document_version"
    ] == "v3"

    assert len(payload["approval_tasks"]) == 1
    assert payload["approval_tasks"][0]["task_type"] == (
        "direct_refund"
    )
    assert payload["approval_tasks"][0]["trace_id"] == str(
        trace_id,
    )

    assert len(payload["audit_logs"]) == 1
    assert payload["audit_logs"][0]["action"] == (
        "create_approval_task"
    )
    assert payload["audit_logs"][0]["trace_id"] == str(
        trace_id,
    )


def test_get_run_detail_returns_empty_related_lists(
    client: TestClient,
    db_session,
) -> None:
    """A valid run without related records returns empty lists."""

    _, thread = create_run_owner(db_session)
    trace_id = uuid4()
    create_agent_run(
        db_session,
        thread,
        trace_id=trace_id,
    )

    response = client.get(
        f"/runs/{trace_id}",
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["trace_id"] == str(trace_id)
    assert payload["nodes"] == []
    assert payload["tool_calls"] == []
    assert payload["messages"] == []
    assert payload["approval_tasks"] == []
    assert payload["audit_logs"] == []


def test_get_run_detail_returns_404_for_missing_trace(
    client: TestClient,
) -> None:
    """A valid but unknown trace_id returns HTTP 404."""

    trace_id = uuid4()

    response = client.get(
        f"/runs/{trace_id}",
    )

    assert response.status_code == 404
    assert str(trace_id) in response.json()["detail"]


def test_get_run_detail_returns_422_for_invalid_trace_format(
    client: TestClient,
) -> None:
    """A malformed trace_id is rejected by FastAPI validation."""

    response = client.get(
        "/runs/not-a-valid-uuid",
    )

    assert response.status_code == 422