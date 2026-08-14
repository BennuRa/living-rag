import json
from uuid import uuid4

import httpx
import pytest

from app.adapters.living_rag import LivingRAGAdapter
from app.schemas.agent_task_case import AgentTaskCase
from app.schemas.fault_injection import FaultInjectionConfig
from app.schemas.run_config import RunConfig


def make_task(
    *,
    expected_route: str = "policy_qa",
    context: dict[str, object] | None = None,
) -> AgentTaskCase:
    return AgentTaskCase(
        case_id="adapter-test-case",
        name="Adapter 测试任务",
        user_input="当前退款政策是什么？",
        context=(
            {"user_external_id": "USR001"}
            if context is None
            else context
        ),
        expected_route=expected_route,
        expected_behavior=["调用正确的目标接口"],
    )


def make_config() -> RunConfig:
    return RunConfig(
        workflow_version="0.1.0",
        timeout_seconds=5.0,
    )


def make_users_response() -> list[dict[str, str]]:
    return [
        {
            "id": "11111111-1111-1111-1111-111111111111",
            "external_id": "USR001",
            "display_name": "测试用户",
        }
    ]


def make_citation_response() -> dict[str, object]:
    return {
        "document_id": str(uuid4()),
        "document_version_id": str(uuid4()),
        "chunk_id": str(uuid4()),
        "document_title": "退款政策",
        "version_number": 3,
        "source_type": "official_policy",
        "governance_status": "active",
        "quote": "普通会员在签收后 15 天内可申请退款。",
        "relevance_score": 0.95,
    }


@pytest.mark.asyncio
async def test_adapter_runs_policy_qa_through_chat_endpoint() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)

        if request.url.path == "/api/users":
            return httpx.Response(
                200,
                json=make_users_response(),
                request=request,
            )

        if request.url.path == "/api/chat":
            assert json.loads(request.content) == {
                "user_id": "11111111-1111-1111-1111-111111111111",
                "question": "当前退款政策是什么？",
            }
            return httpx.Response(
                200,
                json={
                    "trace_id": "trace-policy-001",
                    "answer": "当前有效退款政策为签收后 15 天内。",
                    "citations": [make_citation_response()],
                },
                request=request,
            )

        raise AssertionError(f"Unexpected request path: {request.url.path}")

    transport = httpx.MockTransport(handler)

    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://living-rag.test",
    ) as client:
        adapter = LivingRAGAdapter(client)
        result = await adapter.run(make_task(), make_config())

    assert result.status == "succeeded"
    assert result.final_answer == "当前有效退款政策为签收后 15 天内。"
    assert result.trace_id == "trace-policy-001"
    assert len(result.citations) == 1
    assert result.raw_response is not None
    assert [request.url.path for request in requests] == [
        "/api/users",
        "/api/chat",
    ]


@pytest.mark.asyncio
async def test_adapter_runs_refund_task_through_business_actions() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)

        if request.url.path == "/api/users":
            return httpx.Response(
                200,
                json=make_users_response(),
                request=request,
            )

        if request.url.path == "/api/business-actions":
            assert json.loads(request.content) == {
                "user_id": "11111111-1111-1111-1111-111111111111",
                "question": "当前退款政策是什么？",
            }
            return httpx.Response(
                200,
                json={
                    "trace_id": "trace-business-001",
                    "message": "订单满足退款资格。",
                    "eligibility": {"eligible": True},
                },
                request=request,
            )

        raise AssertionError(f"Unexpected request path: {request.url.path}")

    transport = httpx.MockTransport(handler)

    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://living-rag.test",
    ) as client:
        adapter = LivingRAGAdapter(client)
        result = await adapter.run(
            make_task(expected_route="refund_eligibility"),
            make_config(),
        )

    assert result.status == "succeeded"
    assert result.final_answer == "订单满足退款资格。"
    assert result.trace_id == "trace-business-001"
    assert result.citations == []
    assert [request.url.path for request in requests] == [
        "/api/users",
        "/api/business-actions",
    ]


@pytest.mark.asyncio
async def test_adapter_fails_when_task_has_no_external_user_id() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError(
            f"Adapter should not make a request: {request.url.path}"
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="http://living-rag.test",
    ) as client:
        result = await LivingRAGAdapter(client).run(
            make_task(context={}),
            make_config(),
        )

    assert result.status == "failed"
    assert result.error_message == (
        "Agent task context requires a non-empty user_external_id"
    )


@pytest.mark.asyncio
async def test_adapter_fails_when_external_user_id_is_unknown() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/users"
        return httpx.Response(200, json=[], request=request)

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="http://living-rag.test",
    ) as client:
        result = await LivingRAGAdapter(client).run(
            make_task(),
            make_config(),
        )

    assert result.status == "failed"
    assert result.error_message is not None
    assert "user not found" in result.error_message


@pytest.mark.asyncio
async def test_adapter_rejects_unsupported_route_without_request() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError(
            f"Adapter should not make a request: {request.url.path}"
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="http://living-rag.test",
    ) as client:
        result = await LivingRAGAdapter(client).run(
            make_task(expected_route="unknown_route"),
            make_config(),
        )

    assert result.status == "failed"
    assert result.error_message == (
        "Unsupported Living RAG route: 'unknown_route'"
    )


@pytest.mark.asyncio
async def test_adapter_converts_http_timeout_to_timed_out_result() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/users":
            return httpx.Response(
                200,
                json=make_users_response(),
                request=request,
            )

        raise httpx.ReadTimeout(
            "simulated timeout",
            request=request,
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="http://living-rag.test",
    ) as client:
        result = await LivingRAGAdapter(client).run(
            make_task(),
            make_config(),
        )

    assert result.status == "timed_out"
    assert result.final_answer is None
    assert result.error_message == "Living RAG request timed out"


@pytest.mark.asyncio
async def test_adapter_converts_http_error_to_failed_result() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/users":
            return httpx.Response(
                200,
                json=make_users_response(),
                request=request,
            )

        return httpx.Response(
            500,
            json={"detail": "simulated server error"},
            request=request,
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="http://living-rag.test",
    ) as client:
        result = await LivingRAGAdapter(client).run(
            make_task(),
            make_config(),
        )

    assert result.status == "failed"
    assert result.error_message is not None
    assert "HTTP request failed" in result.error_message


@pytest.mark.asyncio
async def test_adapter_rejects_enabled_fault_without_request() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError(
            f"Adapter should not make a request: {request.url.path}"
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="http://living-rag.test",
    ) as client:
        result = await LivingRAGAdapter(client).run(
            make_task(),
            make_config(),
            fault=FaultInjectionConfig(enabled=True),
        )

    assert result.status == "failed"
    assert result.error_message == (
        "Fault injection is not supported by LivingRAGAdapter yet"
    )


@pytest.mark.asyncio
async def test_adapter_gets_trace_detail() -> None:
    trace_id = "trace-detail-001"

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == f"/runs/{trace_id}"
        return httpx.Response(
            200,
            json={
                "trace_id": trace_id,
                "agent_run": {"status": "succeeded"},
                "nodes": [],
                "tool_calls": [],
                "messages": [],
                "approval_tasks": [],
                "audit_logs": [],
            },
            request=request,
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="http://living-rag.test",
    ) as client:
        trace_detail = await LivingRAGAdapter(client).get_trace(
            trace_id,
            timeout_seconds=5.0,
        )

    assert trace_detail["trace_id"] == trace_id
    assert trace_detail["agent_run"]["status"] == "succeeded"


@pytest.mark.asyncio
async def test_adapter_rejects_blank_trace_id_without_request() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError(
            f"Adapter should not make a request: {request.url.path}"
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="http://living-rag.test",
    ) as client:
        with pytest.raises(ValueError, match="trace_id must not be blank"):
            await LivingRAGAdapter(client).get_trace(
                "   ",
                timeout_seconds=5.0,
            )


@pytest.mark.asyncio
async def test_adapter_rejects_non_object_trace_response() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=[],
            request=request,
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="http://living-rag.test",
    ) as client:
        with pytest.raises(TypeError, match="response must be an object"):
            await LivingRAGAdapter(client).get_trace(
                "trace-detail-001",
                timeout_seconds=5.0,
            )