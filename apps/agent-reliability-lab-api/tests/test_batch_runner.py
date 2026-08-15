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
from app.schemas.fault_injection import FaultInjectionConfig
from app.schemas.run_config import RunConfig
from app.services.batch_runner import BatchCaseRunner
from app.services.case_runner import CaseRunner


class TrackingAdapter:
    def __init__(self, failed_case_id: str | None = None) -> None:
        self._failed_case_id = failed_case_id
        self.currently_running = 0
        self.max_concurrent_calls = 0
        self.call_count = 0

    async def run(
        self,
        task: AgentTaskCase,
        config: RunConfig,
        fault: FaultInjectionConfig | None = None,
    ) -> AgentRunResult:
        self.call_count += 1
        self.currently_running += 1
        self.max_concurrent_calls = max(
            self.max_concurrent_calls,
            self.currently_running,
        )

        try:
            await asyncio.sleep(0.02)

            if task.case_id == self._failed_case_id:
                return AgentRunResult(
                    status="failed",
                    latency_ms=20,
                    error_message="simulated target agent failure",
                )

            return AgentRunResult(
                status="succeeded",
                final_answer=f"回答：{task.case_id}",
                trace_id=f"trace-{task.case_id}",
                latency_ms=20,
            )
        finally:
            self.currently_running -= 1


def make_evaluation_cases(count: int) -> list[EvaluationCase]:
    return [
        EvaluationCase(
            dataset_id=uuid4(),
            task=AgentTaskCase(
                case_id=f"batch-case-{index}",
                name=f"批量任务 {index}",
                user_input=f"请执行批量任务 {index}",
                expected_route="policy_qa",
                expected_behavior=["返回结构化结果"],
            ),
        )
        for index in range(1, count + 1)
    ]


@pytest.mark.asyncio
async def test_batch_case_runner_limits_concurrency_and_keeps_result_order() -> None:
    evaluation_run_id = uuid4()
    evaluation_cases = make_evaluation_cases(5)
    adapter = TrackingAdapter(failed_case_id="batch-case-3")
    config = RunConfig(
        workflow_version="0.1.0",
        timeout_seconds=1,
        max_concurrency=2,
        max_retries=0,
    )
    runner = BatchCaseRunner(CaseRunner(adapter))

    case_runs = await runner.run_cases(
        evaluation_run_id=evaluation_run_id,
        evaluation_cases=evaluation_cases,
        config=config,
    )

    assert adapter.call_count == 5
    assert adapter.max_concurrent_calls == 2
    assert len(case_runs) == 5
    assert [
        case_run.evaluation_case_id
        for case_run in case_runs
    ] == [
        evaluation_case.evaluation_case_id
        for evaluation_case in evaluation_cases
    ]
    assert all(
        case_run.evaluation_run_id == evaluation_run_id
        for case_run in case_runs
    )
    assert [
        case_run.status
        for case_run in case_runs
    ] == [
        EvaluationExecutionStatus.SUCCEEDED,
        EvaluationExecutionStatus.SUCCEEDED,
        EvaluationExecutionStatus.FAILED,
        EvaluationExecutionStatus.SUCCEEDED,
        EvaluationExecutionStatus.SUCCEEDED,
    ]


@pytest.mark.asyncio
async def test_batch_case_runner_returns_empty_list_for_no_cases() -> None:
    adapter = TrackingAdapter()
    config = RunConfig(
        workflow_version="0.1.0",
        timeout_seconds=1,
        max_concurrency=2,
    )
    runner = BatchCaseRunner(CaseRunner(adapter))

    case_runs = await runner.run_cases(
        evaluation_run_id=uuid4(),
        evaluation_cases=[],
        config=config,
    )

    assert case_runs == []
    assert adapter.call_count == 0