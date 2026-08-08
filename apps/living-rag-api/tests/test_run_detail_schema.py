"""Tests for the Living RAG run-detail schemas."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import ValidationError

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
from app.models.tool_call import (
    ToolCall,
    ToolCallStatus,
)
from app.schemas.run_detail import (
    AgentNodeRunDetail,
    AgentRunDetail,
    RunDetailResponse,
)


def build_agent_run() -> AgentRun:
    """Build one ORM AgentRun object without database access."""

    now = datetime(
        2026,
        1,
        1,
        10,
        0,
        tzinfo=UTC,
    )

    return AgentRun(
        id=uuid4(),
        thread_id=uuid4(),
        message_id=uuid4(),
        trace_id=uuid4(),
        status=AgentRunStatus.SUCCEEDED,
        intent="policy_qa",
        workflow_version="0.1.0",
        model_name="mock-llm",
        prompt_version="v1",
        started_at=now,
        completed_at=now + timedelta(seconds=1),
        duration_ms=1000,
        input_tokens=120,
        output_tokens=80,
        estimated_cost=Decimal("0.002500"),
        metadata_={
            "retrieval_count": 2,
            "citation_valid": True,
        },
    )


def build_complete_run_detail_input() -> dict[str, object]:
    """Build ORM records representing one complete Agent Trace."""

    agent_run = build_agent_run()
    trace_id = agent_run.trace_id
    now = datetime(
        2026,
        1,
        1,
        10,
        0,
        2,
        tzinfo=UTC,
    )

    first_node = AgentNodeRun(
        id=uuid4(),
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
        started_at=now,
        completed_at=now + timedelta(milliseconds=10),
        duration_ms=10,
        metadata_={
            "attempt": 1,
        },
    )

    second_node = AgentNodeRun(
        id=uuid4(),
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
        started_at=now + timedelta(milliseconds=10),
        completed_at=now + timedelta(milliseconds=35),
        duration_ms=25,
        metadata_={
            "top_k": 5,
        },
    )

    tool_call = ToolCall(
        id=uuid4(),
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
        started_at=now + timedelta(milliseconds=10),
        completed_at=now + timedelta(milliseconds=25),
        duration_ms=15,
        metadata_={
            "provider": "pgvector",
        },
    )

    user_message = ChatMessage(
        id=uuid4(),
        thread_id=agent_run.thread_id,
        sequence_number=1,
        role=ChatMessageRole.USER,
        content="当前退款政策是多少天？",
        status=ChatMessageStatus.COMPLETED,
        trace_id=trace_id,
        citations=[],
        metadata_={
            "source": "chat",
        },
        created_at=now + timedelta(seconds=1),
        updated_at=now + timedelta(seconds=1),
    )

    assistant_message = ChatMessage(
        id=uuid4(),
        thread_id=agent_run.thread_id,
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
        created_at=now + timedelta(seconds=2),
        updated_at=now + timedelta(seconds=2),
    )

    approval_task = ApprovalTask(
        id=uuid4(),
        task_type=ApprovalTaskType.DIRECT_REFUND,
        status=ApprovalTaskStatus.PENDING,
        resource_type="refund_request",
        resource_id=None,
        requested_by=uuid4(),
        trace_id=trace_id,
        reason="Direct refund requires human approval.",
        created_at=now + timedelta(seconds=3),
        updated_at=now + timedelta(seconds=3),
        metadata_={
            "risk_level": "high",
        },
    )

    audit_log = AuditLog(
        id=uuid4(),
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
        created_at=now + timedelta(seconds=4),
        metadata_={
            "source": "business_action",
        },
    )

    return {
        "trace_id": trace_id,
        "agent_run": agent_run,
        "nodes": [
            first_node,
            second_node,
        ],
        "tool_calls": [
            tool_call,
        ],
        "messages": [
            user_message,
            assistant_message,
        ],
        "approval_tasks": [
            approval_task,
        ],
        "audit_logs": [
            audit_log,
        ],
    }


def test_run_detail_schema_validates_complete_orm_objects() -> None:
    """Complete ORM run data can be converted into the response schema."""

    detail_input = build_complete_run_detail_input()

    response = RunDetailResponse.model_validate(detail_input)

    assert response.trace_id == detail_input["trace_id"]
    assert response.agent_run.status == AgentRunStatus.SUCCEEDED
    assert response.agent_run.workflow_version == "0.1.0"
    assert response.agent_run.input_tokens == 120
    assert response.agent_run.output_tokens == 80
    assert response.agent_run.estimated_cost == Decimal("0.002500")

    assert len(response.nodes) == 2
    assert response.nodes[0].node_name == "classify_intent"
    assert response.nodes[1].node_name == "retrieve_documents"
    assert response.nodes[1].input_snapshot["intent"] == "policy_qa"

    assert len(response.tool_calls) == 1
    assert response.tool_calls[0].tool_name == "search_documents"
    assert (
        response.tool_calls[0].node_run_id
        == response.nodes[1].id
    )

    assert len(response.messages) == 2
    assert response.messages[0].role == ChatMessageRole.USER
    assert response.messages[1].role == ChatMessageRole.ASSISTANT
    assert response.messages[1].citations[0]["document_version"] == "v3"

    assert len(response.approval_tasks) == 1
    assert (
        response.approval_tasks[0].task_type
        == ApprovalTaskType.DIRECT_REFUND
    )

    assert len(response.audit_logs) == 1
    assert response.audit_logs[0].action == "create_approval_task"


def test_run_detail_schema_serializes_metadata_without_underscore() -> None:
    """ORM metadata_ attributes are exposed as API metadata fields."""

    detail_input = build_complete_run_detail_input()

    response = RunDetailResponse.model_validate(detail_input)
    serialized = response.model_dump(
        mode="json",
        by_alias=True,
    )

    assert serialized["agent_run"]["metadata"] == {
        "retrieval_count": 2,
        "citation_valid": True,
    }
    assert "metadata_" not in serialized["agent_run"]

    assert serialized["nodes"][0]["metadata"] == {
        "attempt": 1,
    }
    assert serialized["tool_calls"][0]["metadata"] == {
        "provider": "pgvector",
    }
    assert serialized["messages"][0]["metadata"] == {
        "source": "chat",
    }
    assert serialized["approval_tasks"][0]["metadata"] == {
        "risk_level": "high",
    }
    assert serialized["audit_logs"][0]["metadata"] == {
        "source": "business_action",
    }


def test_run_detail_schema_uses_empty_lists_for_missing_related_data() -> None:
    """Missing related collections are represented as empty lists."""

    agent_run = build_agent_run()

    response = RunDetailResponse.model_validate(
        {
            "trace_id": agent_run.trace_id,
            "agent_run": agent_run,
        },
    )

    assert response.nodes == []
    assert response.tool_calls == []
    assert response.messages == []
    assert response.approval_tasks == []
    assert response.audit_logs == []


def test_run_detail_schema_rejects_invalid_node_duration() -> None:
    """A negative node duration must fail schema validation."""

    node = AgentNodeRunDetail(
        id=uuid4(),
        agent_run_id=uuid4(),
        node_name="retrieve_documents",
        sequence_number=1,
        status=AgentNodeRunStatus.SUCCEEDED,
        input_snapshot={},
        output_snapshot={},
        started_at=None,
        completed_at=None,
        duration_ms=10,
        error_code=None,
        error_message=None,
        metadata={},
    )

    assert node.duration_ms == 10

    with pytest.raises(ValidationError):
        AgentNodeRunDetail(
            id=uuid4(),
            agent_run_id=uuid4(),
            node_name="retrieve_documents",
            sequence_number=1,
            status=AgentNodeRunStatus.SUCCEEDED,
            input_snapshot={},
            output_snapshot={},
            started_at=None,
            completed_at=None,
            duration_ms=-1,
            error_code=None,
            error_message=None,
            metadata={},
        )


def test_agent_run_detail_rejects_extra_fields() -> None:
    """The AgentRun response must reject fields outside the contract."""

    agent_run = build_agent_run()

    with pytest.raises(ValidationError):
        AgentRunDetail.model_validate(
            {
                "id": agent_run.id,
                "thread_id": agent_run.thread_id,
                "message_id": agent_run.message_id,
                "trace_id": agent_run.trace_id,
                "status": agent_run.status,
                "workflow_version": agent_run.workflow_version,
                "unexpected_field": "must be rejected",
            },
        )