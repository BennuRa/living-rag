from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas.agent_run_result import AgentRunResult
from app.schemas.citation import Citation


def make_citation() -> Citation:
    return Citation(
        document_id=uuid4(),
        document_version_id=uuid4(),
        chunk_id=uuid4(),
        quote="普通会员在签收后 15 天内可申请退款。",
    )


def test_succeeded_result_accepts_answer_and_citations() -> None:
    result = AgentRunResult(
        status="succeeded",
        final_answer="订单满足退款资格。",
        citations=[make_citation()],
        trace_id="trace-001",
        latency_ms=123.4,
        raw_response={"answer": "订单满足退款资格。"},
    )

    assert result.status == "succeeded"
    assert result.final_answer == "订单满足退款资格。"
    assert len(result.citations) == 1
    assert result.error_message is None


def test_each_result_gets_its_own_citations_list() -> None:
    first_result = AgentRunResult(
        status="succeeded",
        final_answer="第一条回答。",
        latency_ms=1.0,
    )
    second_result = AgentRunResult(
        status="succeeded",
        final_answer="第二条回答。",
        latency_ms=1.0,
    )

    first_result.citations.append(make_citation())

    assert len(first_result.citations) == 1
    assert second_result.citations == []


@pytest.mark.parametrize("status", ["failed", "timed_out"])
def test_failed_results_require_an_error_message(status: str) -> None:
    result = AgentRunResult(
        status=status,
        latency_ms=30.0,
        error_message="订单查询服务暂时不可用。",
    )

    assert result.status == status
    assert result.final_answer is None


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        (
            {
                "status": "succeeded",
                "latency_ms": 1.0,
            },
            "succeeded result requires a non-empty final_answer",
        ),
        (
            {
                "status": "succeeded",
                "final_answer": "退款资格查询完成。",
                "latency_ms": 1.0,
                "error_message": "不应该出现的错误",
            },
            "succeeded result cannot include an error_message",
        ),
        (
            {
                "status": "failed",
                "latency_ms": 1.0,
            },
            "failed or timed_out result requires a non-empty error_message",
        ),
        (
            {
                "status": "timed_out",
                "latency_ms": 1.0,
                "error_message": "   ",
            },
            "failed or timed_out result requires a non-empty error_message",
        ),
        (
            {
                "status": "succeeded",
                "final_answer": "正常回答。",
                "latency_ms": -0.1,
            },
            "Input should be greater than or equal to 0",
        ),
    ],
)
def test_agent_run_result_rejects_invalid_state(
    kwargs: dict[str, object],
    message: str,
) -> None:
    with pytest.raises(ValidationError, match=message):
        AgentRunResult(**kwargs)