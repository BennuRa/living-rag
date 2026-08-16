from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.trace_replay import (
    TraceApprovalTask,
    TraceAuditLog,
    TraceMessage,
    TraceNode,
    TraceReplay,
    TraceToolCall,
)


def test_trace_replay_builds_minimal_empty_trace() -> None:
    trace = TraceReplay(
        trace_id="trace-demo",
        run_status="succeeded",
    )

    assert trace.trace_id == "trace-demo"
    assert trace.run_status == "succeeded"
    assert trace.messages == []
    assert trace.nodes == []
    assert trace.tool_calls == []
    assert trace.approval_tasks == []
    assert trace.audit_logs == []
    assert trace.citations == []


def test_trace_replay_builds_nested_execution_details() -> None:
    trace = TraceReplay(
        trace_id="trace-demo",
        run_status="succeeded",
        intent="order_membership",
        workflow_version="0.1.0",
        final_answer="订单符合当前退款条件",
        messages=[
            TraceMessage(
                role="user",
                content="订单可以退款吗？",
            ),
            TraceMessage(
                role="assistant",
                content="订单符合当前退款条件",
            ),
        ],
        nodes=[
            TraceNode(
                node_name="classify_intent",
                status="succeeded",
                latency_ms=12.5,
            ),
        ],
        tool_calls=[
            TraceToolCall(
                tool_name="get_order",
                status="succeeded",
                latency_ms=8.2,
            ),
        ],
        approval_tasks=[
            TraceApprovalTask(
                approval_task_id="approval-demo",
                status="pending",
                action="refund",
            ),
        ],
        audit_logs=[
            TraceAuditLog(
                action="create_approval_task",
                status="recorded",
                actor="agent",
            ),
        ],
        citations=[
            {
                "document_id": "document-demo",
                "chunk_id": "chunk-demo",
            }
        ],
    )

    assert trace.intent == "order_membership"
    assert trace.workflow_version == "0.1.0"
    assert trace.final_answer == "订单符合当前退款条件"
    assert len(trace.messages) == 2
    assert trace.messages[0].role == "user"
    assert trace.nodes[0].node_name == "classify_intent"
    assert trace.tool_calls[0].tool_name == "get_order"
    assert trace.approval_tasks[0].status == "pending"
    assert trace.audit_logs[0].action == "create_approval_task"
    assert trace.citations[0]["chunk_id"] == "chunk-demo"


@pytest.mark.parametrize(
    ("model", "kwargs"),
    [
        (
            TraceReplay,
            {
                "trace_id": "",
                "run_status": "succeeded",
            },
        ),
        (
            TraceMessage,
            {
                "role": "",
                "content": "content",
            },
        ),
        (
            TraceNode,
            {
                "node_name": "",
            },
        ),
        (
            TraceToolCall,
            {
                "tool_name": "",
            },
        ),
        (
            TraceApprovalTask,
            {
                "approval_task_id": "",
            },
        ),
        (
            TraceAuditLog,
            {
                "action": "",
            },
        ),
    ],
)
def test_trace_replay_rejects_required_blank_fields(
    model: type[object],
    kwargs: dict[str, object],
) -> None:
    with pytest.raises(ValidationError):
        model(**kwargs)


@pytest.mark.parametrize(
    "model",
    [
        TraceNode,
        TraceToolCall,
    ],
)
def test_trace_replay_rejects_negative_latency(
    model: type[object],
) -> None:
    field_name = (
        "node_name"
        if model is TraceNode
        else "tool_name"
    )
    valid_kwargs = {
        field_name: "demo",
        "latency_ms": -0.01,
    }

    with pytest.raises(ValidationError):
        model(**valid_kwargs)


def test_trace_replay_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        TraceReplay(
            trace_id="trace-demo",
            run_status="succeeded",
            unknown_field="unexpected",
        )


def test_trace_replay_serializes_empty_collections() -> None:
    trace = TraceReplay(
        trace_id="trace-demo",
        run_status="succeeded",
    )

    payload = trace.model_dump()

    assert payload["messages"] == []
    assert payload["nodes"] == []
    assert payload["tool_calls"] == []
    assert payload["approval_tasks"] == []
    assert payload["audit_logs"] == []
    assert payload["citations"] == []