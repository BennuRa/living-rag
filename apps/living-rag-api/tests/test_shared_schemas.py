from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas.agent_task_case import AgentTaskCase
from app.schemas.agent_trace import (
    AgentNodeTrace,
    AgentTrace,
    ToolCallTrace,
)
from app.schemas.citation import Citation
from app.schemas.fault_injection import (
    FaultInjectionConfig,
    FaultInjectionType,
)


def test_create_citation_with_valid_evidence() -> None:
    """A citation keeps document, version, chunk, and quote data."""

    document_id = uuid4()
    document_version_id = uuid4()
    chunk_id = uuid4()

    citation = Citation(
        document_id=document_id,
        document_version_id=document_version_id,
        chunk_id=chunk_id,
        quote="普通会员签收后 7 天内可以申请退款。",
        relevance_score=0.94,
    )

    assert citation.document_id == document_id
    assert citation.document_version_id == document_version_id
    assert citation.chunk_id == chunk_id
    assert citation.quote == "普通会员签收后 7 天内可以申请退款。"
    assert citation.relevance_score == 0.94


def test_reject_invalid_citation_relevance_score() -> None:
    """A citation relevance score must stay between zero and one."""

    with pytest.raises(ValidationError):
        Citation(
            document_id=uuid4(),
            document_version_id=uuid4(),
            chunk_id=uuid4(),
            quote="有效引用内容",
            relevance_score=1.5,
        )


def test_create_agent_trace_with_nodes_and_tool_calls() -> None:
    """An Agent trace can contain node and tool execution summaries."""

    trace_id = uuid4()
    agent_run_id = uuid4()

    trace = AgentTrace(
        trace_id=trace_id,
        agent_run_id=agent_run_id,
        status="succeeded",
        intent="refund_policy",
        workflow_version="0.1.0",
        model_name="mock-model",
        prompt_version="v1",
        duration_ms=850,
        nodes=[
            AgentNodeTrace(
                node_name="retrieve_documents",
                sequence_number=1,
                status="succeeded",
                duration_ms=300,
            ),
        ],
        tool_calls=[
            ToolCallTrace(
                tool_name="search_documents",
                status="succeeded",
                duration_ms=280,
            ),
        ],
    )

    assert trace.trace_id == trace_id
    assert trace.agent_run_id == agent_run_id
    assert len(trace.nodes) == 1
    assert trace.nodes[0].node_name == "retrieve_documents"
    assert len(trace.tool_calls) == 1
    assert trace.tool_calls[0].tool_name == "search_documents"


def test_create_agent_task_case_with_generated_id() -> None:
    """An Agent task case receives a generated identifier by default."""

    task_case = AgentTaskCase(
        name="当前退款政策问答",
        user_input="普通会员签收后多久可以申请退款？",
        expected_intent="refund_policy",
        expected_behavior="必须引用当前有效的退款政策。",
        tags=["refund", "policy"],
    )

    assert task_case.case_id is not None
    assert task_case.name == "当前退款政策问答"
    assert task_case.expected_intent == "refund_policy"
    assert task_case.tags == ["refund", "policy"]
    assert task_case.metadata == {}


def test_create_fault_injection_config() -> None:
    """A fault injection config keeps deterministic failure settings."""

    config = FaultInjectionConfig(
        enabled=True,
        fault_type=FaultInjectionType.TOOL_TIMEOUT,
        target_tool="search_documents",
        message="模拟检索工具超时",
        parameters={
            "timeout_ms": 100,
        },
    )

    assert config.enabled is True
    assert config.fault_type is FaultInjectionType.TOOL_TIMEOUT
    assert config.target_tool == "search_documents"
    assert config.parameters == {
        "timeout_ms": 100,
    }


def test_reject_unknown_schema_fields() -> None:
    """Shared schemas reject undeclared fields."""

    with pytest.raises(ValidationError):
        Citation(
            document_id=uuid4(),
            document_version_id=uuid4(),
            chunk_id=uuid4(),
            quote="有效引用内容",
            unsupported_field="not allowed",
        )