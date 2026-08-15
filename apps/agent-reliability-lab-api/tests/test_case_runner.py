from __future__ import annotations

import asyncio
from uuid import uuid4

import pytest

from app.schemas.agent_run_result import AgentRunResult
from app.schemas.agent_task_case import AgentTaskCase
from app.schemas.evaluation_entities import (
    EvaluationCase,
    EvaluationExecutionStatus,
)
from app.schemas.fault_injection import (
    FaultInjectionConfig,
    FaultInjectionType,
)
from app.schemas.run_config import RunConfig
from app.services.case_runner import CaseRunner


class FakeAdapter:
    def __init__(
        self,
        result: AgentRunResult | None = None,
        error: Exception | None = None,
    ) -> None:
        self._result = result
        self._error = error
        self.received_task: AgentTaskCase | None = None
        self.received_config: RunConfig | None = None
        self.received_fault: FaultInjectionConfig | None = None

    async def run(
        self,
        task: AgentTaskCase,
        config: RunConfig,
        fault: FaultInjectionConfig | None = None,
    ) -> AgentRunResult:
        self.received_task = task
        self.received_config = config
        self.received_fault = fault

        if self._error is not None:
            raise self._error

        assert self._result is not None
        return self._result


def make_evaluation_case() -> EvaluationCase:
    task = AgentTaskCase(
        case_id="case-runner-001",
        name="CaseRunner 测试任务",
        user_input="订单 O2025001 可以退款吗？",
        expected_route="refund_eligibility",
        expected_behavior=["返回退款资格判断"],
    )

    return EvaluationCase(
        dataset_id=uuid4(),
        task=task,
    )


def make_config() -> RunConfig:
    return RunConfig(
        workflow_version="0.1.0",
        timeout_seconds=30,
    )


@pytest.mark.asyncio
async def test_case_runner_records_successful_result() -> None:
    evaluation_run_id = uuid4()
    evaluation_case = make_evaluation_case()
    result = AgentRunResult(
        status="succeeded",
        final_answer="订单符合当前退款条件。",
        trace_id="trace-success",
        latency_ms=85.2,
    )
    adapter = FakeAdapter(result=result)

    case_run = await CaseRunner(adapter).run_case(
        evaluation_run_id=evaluation_run_id,
        evaluation_case=evaluation_case,
        config=make_config(),
    )

    assert case_run.evaluation_run_id == evaluation_run_id
    assert case_run.evaluation_case_id == evaluation_case.evaluation_case_id
    assert case_run.status == EvaluationExecutionStatus.SUCCEEDED
    assert case_run.attempt_count == 1
    assert case_run.result == result
    assert case_run.trace_id == "trace-success"
    assert case_run.latency_ms == 85.2
    assert case_run.error_message is None
    assert case_run.started_at is not None
    assert case_run.completed_at is not None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("result_status", "expected_status", "expected_attempt_count"),
    [
        (
            "failed",
            EvaluationExecutionStatus.FAILED,
            1,
        ),
        (
            "timed_out",
            EvaluationExecutionStatus.TIMED_OUT,
            2,
        ),
    ],
)
async def test_case_runner_maps_unsuccessful_agent_results(
    result_status: str,
    expected_status: EvaluationExecutionStatus,
    expected_attempt_count: int,
) -> None:
    result = AgentRunResult(
        status=result_status,
        latency_ms=50,
        error_message="simulated target agent failure",
    )
    adapter = FakeAdapter(result=result)

    case_run = await CaseRunner(adapter).run_case(
        evaluation_run_id=uuid4(),
        evaluation_case=make_evaluation_case(),
        config=make_config(),
    )

    assert case_run.status == expected_status
    assert case_run.attempt_count == expected_attempt_count
    assert case_run.result == result
    assert case_run.error_message == "simulated target agent failure"


@pytest.mark.asyncio
async def test_case_runner_converts_adapter_exception_to_failed_case_run() -> None:
    adapter = FakeAdapter(
        error=RuntimeError("simulated adapter crash"),
    )

    case_run = await CaseRunner(adapter).run_case(
        evaluation_run_id=uuid4(),
        evaluation_case=make_evaluation_case(),
        config=make_config(),
    )

    assert case_run.status == EvaluationExecutionStatus.FAILED
    assert case_run.attempt_count == 2
    assert case_run.result is None
    assert case_run.trace_id is None
    assert case_run.latency_ms is None
    assert case_run.error_message == "RuntimeError: simulated adapter crash"
    assert case_run.started_at is not None
    assert case_run.completed_at is not None


@pytest.mark.asyncio
async def test_case_runner_forwards_fault_config_to_adapter() -> None:
    evaluation_case = make_evaluation_case()
    config = make_config()
    fault = FaultInjectionConfig(
        enabled=True,
        fault_type=FaultInjectionType.TOOL_TIMEOUT,
    )
    adapter = FakeAdapter(
        result=AgentRunResult(
            status="succeeded",
            final_answer="模拟故障后的安全回答。",
            latency_ms=20,
        )
    )

    await CaseRunner(adapter).run_case(
        evaluation_run_id=uuid4(),
        evaluation_case=evaluation_case,
        config=config,
        fault=fault,
    )

    assert adapter.received_task == evaluation_case.task
    assert adapter.received_config == config
    assert adapter.received_fault == fault


class SlowAdapter:
    async def run(
        self,
        task: AgentTaskCase,
        config: RunConfig,
        fault: FaultInjectionConfig | None = None,
    ) -> AgentRunResult:
        await asyncio.sleep(0.05)

        return AgentRunResult(
            status="succeeded",
            final_answer="这条结果不应该在超时测试中返回。",
            latency_ms=50,
        )


@pytest.mark.asyncio
async def test_case_runner_marks_slow_adapter_as_timed_out() -> None:
    config = RunConfig(
        workflow_version="0.1.0",
        timeout_seconds=0.01,
    )

    case_run = await CaseRunner(SlowAdapter()).run_case(
        evaluation_run_id=uuid4(),
        evaluation_case=make_evaluation_case(),
        config=config,
    )

    assert case_run.status == EvaluationExecutionStatus.TIMED_OUT
    assert case_run.attempt_count == 2
    assert case_run.result is None
    assert case_run.trace_id is None
    assert case_run.latency_ms is None
    assert case_run.error_message == "Case execution exceeded 0.01 seconds"
    assert case_run.started_at is not None
    assert case_run.completed_at is not None


class SequenceAdapter:
    def __init__(
        self,
        outcomes: list[AgentRunResult | Exception],
    ) -> None:
        self._outcomes = outcomes
        self.call_count = 0

    async def run(
        self,
        task: AgentTaskCase,
        config: RunConfig,
        fault: FaultInjectionConfig | None = None,
    ) -> AgentRunResult:
        outcome = self._outcomes[self.call_count]
        self.call_count += 1

        if isinstance(outcome, Exception):
            raise outcome

        return outcome


@pytest.mark.asyncio
async def test_case_runner_retries_adapter_exception_then_succeeds() -> None:
    successful_result = AgentRunResult(
        status="succeeded",
        final_answer="第二次调用成功。",
        trace_id="trace-retry-success",
        latency_ms=80,
    )
    adapter = SequenceAdapter(
        outcomes=[
            RuntimeError("temporary adapter failure"),
            successful_result,
        ]
    )

    case_run = await CaseRunner(adapter).run_case(
        evaluation_run_id=uuid4(),
        evaluation_case=make_evaluation_case(),
        config=make_config(),
    )

    assert adapter.call_count == 2
    assert case_run.status == EvaluationExecutionStatus.SUCCEEDED
    assert case_run.attempt_count == 2
    assert case_run.result == successful_result
    assert case_run.trace_id == "trace-retry-success"
    assert case_run.error_message is None


@pytest.mark.asyncio
async def test_case_runner_retries_target_timeout_then_succeeds() -> None:
    successful_result = AgentRunResult(
        status="succeeded",
        final_answer="重试后成功得到回答。",
        trace_id="trace-timeout-recovered",
        latency_ms=60,
    )
    adapter = SequenceAdapter(
        outcomes=[
            AgentRunResult(
                status="timed_out",
                latency_ms=30000,
                error_message="target agent timed out",
            ),
            successful_result,
        ]
    )

    case_run = await CaseRunner(adapter).run_case(
        evaluation_run_id=uuid4(),
        evaluation_case=make_evaluation_case(),
        config=make_config(),
    )

    assert adapter.call_count == 2
    assert case_run.status == EvaluationExecutionStatus.SUCCEEDED
    assert case_run.attempt_count == 2
    assert case_run.result == successful_result
    assert case_run.trace_id == "trace-timeout-recovered"
    assert case_run.error_message is None


@pytest.mark.asyncio
async def test_case_runner_does_not_retry_when_max_retries_is_zero() -> None:
    adapter = SequenceAdapter(
        outcomes=[
            RuntimeError("temporary adapter failure"),
        ]
    )
    config = RunConfig(
        workflow_version="0.1.0",
        timeout_seconds=30,
        max_retries=0,
    )

    case_run = await CaseRunner(adapter).run_case(
        evaluation_run_id=uuid4(),
        evaluation_case=make_evaluation_case(),
        config=config,
    )

    assert adapter.call_count == 1
    assert case_run.status == EvaluationExecutionStatus.FAILED
    assert case_run.attempt_count == 1
    assert case_run.error_message == "RuntimeError: temporary adapter failure"