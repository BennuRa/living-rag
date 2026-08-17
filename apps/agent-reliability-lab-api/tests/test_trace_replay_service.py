from __future__ import annotations

from app.services.trace_replay_service import TraceReplayService


def test_service_builds_minimal_trace_replay() -> None:
    raw_trace = {
        "trace_id": "trace-minimal",
        "agent_run": {
            "status": "succeeded",
            "intent": "order_membership",
            "workflow_version": "0.1.0",
        },
        "messages": [
            {
                "role": "user",
                "content": "订单可以退款吗？",
            },
            {
                "role": "assistant",
                "content": "订单符合当前退款条件",
            },
        ],
    }

    replay = TraceReplayService().build_replay(raw_trace)

    assert replay.trace_id == "trace-minimal"
    assert replay.run_status == "succeeded"
    assert replay.intent == "order_membership"
    assert replay.workflow_version == "0.1.0"
    assert replay.action is None
    assert replay.approval_task_id is None
    assert replay.refund_request_id is None
    assert replay.final_answer == "订单符合当前退款条件"
    assert replay.messages[0].role == "user"
    assert replay.nodes == []
    assert replay.tool_calls == []
    assert replay.approval_tasks == []
    assert replay.audit_logs == []
    assert replay.citations == []


def test_service_maps_full_trace_details() -> None:
    raw_trace = {
        "trace_id": "trace-full",
        "agent_run": {
            "status": "succeeded",
            "intent": "refund_request",
            "workflow_version": "0.1.0",
            "final_answer": "已创建人工审批任务",
            "metadata": {
                "action": "create_approval_task",
                "approval_task_id": "approval-001",
                "refund_request_id": None,
                "retrieval_status": "succeeded",
                "conflict_status": "none",
            },
        },
        "messages": [
            {
                "role": "user",
                "content": "我要申请退款",
                "created_at": "2026-08-16T08:00:00Z",
            },
            {
                "role": "assistant",
                "content": "已创建人工审批任务",
                "created_at": "2026-08-16T08:00:01Z",
            },
        ],
        "nodes": [
            {
                "name": "classify_intent",
                "status": "succeeded",
                "latency_ms": 4.5,
                "input": {"question": "我要申请退款"},
                "output": {"intent": "refund_request"},
                "started_at": "2026-08-16T08:00:00Z",
                "completed_at": "2026-08-16T08:00:00.500000Z",
            }
        ],
        "tool_calls": [
            {
                "name": "get_order",
                "status": "succeeded",
                "latency_ms": 8,
                "input": {"order_no": "O2025001"},
                "output": {"eligible": True},
            }
        ],
        "approval_tasks": [
            {
                "id": "approval-001",
                "status": "pending",
                "action": "refund",
                "reason": "用户请求直接退款",
                "created_at": "2026-08-16T08:00:02Z",
            }
        ],
        "audit_logs": [
            {
                "action": "create_approval_task",
                "status": "succeeded",
                "actor": "agent",
                "detail": {"approval_task_id": "approval-001"},
                "created_at": "2026-08-16T08:00:02Z",
            }
        ],
        "citations": [
            {
                "chunk_id": "chunk-001",
                "document_version": 3,
            }
        ],
    }

    replay = TraceReplayService().build_replay(raw_trace)

    assert replay.final_answer == "已创建人工审批任务"
    assert replay.action == "create_approval_task"
    assert replay.approval_task_id == "approval-001"
    assert replay.refund_request_id is None
    assert replay.retrieval_status == "succeeded"
    assert replay.conflict_status == "none"
    assert replay.messages[0].created_at is not None

    assert len(replay.nodes) == 1
    assert replay.nodes[0].node_name == "classify_intent"
    assert replay.nodes[0].latency_ms == 4.5
    assert '"intent": "refund_request"' in (replay.nodes[0].output_summary or "")

    assert len(replay.tool_calls) == 1
    assert replay.tool_calls[0].tool_name == "get_order"
    assert replay.tool_calls[0].latency_ms == 8.0
    assert '"order_no": "O2025001"' in (replay.tool_calls[0].input_summary or "")

    assert len(replay.approval_tasks) == 1
    assert replay.approval_tasks[0].approval_task_id == "approval-001"
    assert replay.approval_tasks[0].status == "pending"

    assert len(replay.audit_logs) == 1
    assert replay.audit_logs[0].action == "create_approval_task"
    assert '"approval_task_id": "approval-001"' in (replay.audit_logs[0].detail or "")

    assert replay.citations[0]["chunk_id"] == "chunk-001"


def test_service_uses_top_level_fields_and_missing_collections() -> None:
    raw_trace = {
        "trace_id": "trace-top-level",
        "run_status": "failed",
        "intent": "policy_qa",
        "workflow_version": "0.2.0",
        "final_answer": "暂时无法回答",
    }

    replay = TraceReplayService().build_replay(raw_trace)

    assert replay.run_status == "failed"
    assert replay.intent == "policy_qa"
    assert replay.workflow_version == "0.2.0"
    assert replay.final_answer == "暂时无法回答"
    assert replay.messages == []
    assert replay.nodes == []
    assert replay.tool_calls == []
    assert replay.approval_tasks == []
    assert replay.audit_logs == []
    assert replay.citations == []


def test_service_rejects_missing_trace_id() -> None:
    raw_trace = {
        "agent_run": {
            "status": "succeeded",
        },
    }

    try:
        TraceReplayService().build_replay(raw_trace)
    except ValueError as exc:
        assert "trace_id" in str(exc)
    else:
        raise AssertionError("Expected missing trace_id to be rejected")


def test_service_rejects_non_list_collection() -> None:
    raw_trace = {
        "trace_id": "trace-invalid",
        "messages": {},
    }

    try:
        TraceReplayService().build_replay(raw_trace)
    except TypeError as exc:
        assert "messages" in str(exc)
    else:
        raise AssertionError("Expected non-list messages to be rejected")


def test_service_rejects_non_object_agent_run_metadata() -> None:
    raw_trace = {
        "trace_id": "trace-invalid-metadata",
        "agent_run": {
            "metadata": "not-an-object",
        },
    }

    try:
        TraceReplayService().build_replay(raw_trace)
    except TypeError as exc:
        assert "metadata" in str(exc)
    else:
        raise AssertionError("Expected non-object metadata to be rejected")


def test_service_rejects_node_without_name() -> None:
    raw_trace = {
        "trace_id": "trace-invalid-node",
        "nodes": [
            {
                "status": "succeeded",
            }
        ],
    }

    try:
        TraceReplayService().build_replay(raw_trace)
    except ValueError as exc:
        assert "node_name" in str(exc)
    else:
        raise AssertionError("Expected node without name to be rejected")


def test_service_rejects_invalid_latency() -> None:
    raw_trace = {
        "trace_id": "trace-invalid-latency",
        "nodes": [
            {
                "node_name": "retrieve_documents",
                "latency_ms": "slow",
            }
        ],
    }

    try:
        TraceReplayService().build_replay(raw_trace)
    except TypeError as exc:
        assert "latency" in str(exc)
    else:
        raise AssertionError("Expected invalid latency to be rejected")


def test_service_rejects_invalid_datetime() -> None:
    raw_trace = {
        "trace_id": "trace-invalid-time",
        "messages": [
            {
                "role": "assistant",
                "content": "回答",
                "created_at": "not-a-datetime",
            }
        ],
    }

    try:
        TraceReplayService().build_replay(raw_trace)
    except ValueError as exc:
        assert "datetime" in str(exc)
    else:
        raise AssertionError("Expected invalid datetime to be rejected")
