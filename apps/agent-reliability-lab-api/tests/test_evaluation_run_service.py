from __future__ import annotations

from pathlib import Path

import pytest

from app.schemas.agent_task_case import AgentTaskCase
from app.schemas.evaluation_entities import (
    CaseRun,
    EvaluationCase,
    EvaluationDataset,
    EvaluationExecutionStatus,
)
from app.schemas.fault_injection import (
    FaultInjectionConfig,
    FaultInjectionType,
)
from app.schemas.run_config import RunConfig
from app.services.evaluation_run_service import EvaluationRunService
from app.services.run_artifact_store import EvaluationRunArtifactStore


class FakeBatchCaseRunner:
    def __init__(
        self,
        statuses: list[EvaluationExecutionStatus],
    ) -> None:
        self._statuses = statuses
        self.call_count = 0
        self.received_evaluation_run_id = None
        self.received_evaluation_cases: list[EvaluationCase] | None = None
        self.received_config: RunConfig | None = None
        self.received_fault: FaultInjectionConfig | None = None

    async def run_cases(
        self,
        evaluation_run_id,
        evaluation_cases: list[EvaluationCase],
        config: RunConfig,
        fault: FaultInjectionConfig | None = None,
    ) -> list[CaseRun]:
        self.call_count += 1
        self.received_evaluation_run_id = evaluation_run_id
        self.received_evaluation_cases = evaluation_cases
        self.received_config = config
        self.received_fault = fault

        return [
            CaseRun(
                evaluation_run_id=evaluation_run_id,
                evaluation_case_id=evaluation_case.evaluation_case_id,
                status=status,
                attempt_count=1,
            )
            for evaluation_case, status in zip(
                evaluation_cases,
                self._statuses,
                strict=True,
            )
        ]


def make_dataset() -> EvaluationDataset:
    return EvaluationDataset(
        name="evaluation-run-service-test",
        source_path="tests/data/evaluation-run-service-test.jsonl",
        version="1",
    )


def make_evaluation_cases(
    dataset: EvaluationDataset,
    count: int,
) -> list[EvaluationCase]:
    return [
        EvaluationCase(
            dataset_id=dataset.dataset_id,
            task=AgentTaskCase(
                case_id=f"run-service-case-{index}",
                name=f"运行服务测试案例 {index}",
                user_input=f"执行案例 {index}",
                expected_route="policy_qa",
                expected_behavior=["返回测试结果"],
            ),
        )
        for index in range(1, count + 1)
    ]


def make_config() -> RunConfig:
    return RunConfig(
        workflow_version="0.1.0",
        timeout_seconds=30,
        max_concurrency=2,
        max_retries=1,
    )


@pytest.mark.asyncio
async def test_evaluation_run_service_executes_cases_and_summarizes_results(
    tmp_path: Path,
) -> None:
    dataset = make_dataset()
    evaluation_cases = make_evaluation_cases(dataset, 5)
    fault = FaultInjectionConfig(
        enabled=True,
        fault_type=FaultInjectionType.TOOL_TIMEOUT,
    )
    batch_case_runner = FakeBatchCaseRunner(
        statuses=[
            EvaluationExecutionStatus.SUCCEEDED,
            EvaluationExecutionStatus.SUCCEEDED,
            EvaluationExecutionStatus.FAILED,
            EvaluationExecutionStatus.TIMED_OUT,
            EvaluationExecutionStatus.SUCCEEDED,
        ]
    )

    artifact_store = EvaluationRunArtifactStore(
        tmp_path / "evaluation-runs",
    )

    service = EvaluationRunService(
        batch_case_runner=batch_case_runner,
        artifact_store=artifact_store,
    )

    evaluation_run, case_runs = await service.execute(
        dataset=dataset,
        evaluation_cases=evaluation_cases,
        config=make_config(),
        fault=fault,
    )

    assert batch_case_runner.call_count == 1
    assert (
        batch_case_runner.received_evaluation_run_id
        == evaluation_run.evaluation_run_id
    )
    assert batch_case_runner.received_evaluation_cases == evaluation_cases
    assert batch_case_runner.received_config == make_config()
    assert batch_case_runner.received_fault == fault

    assert evaluation_run.dataset_id == dataset.dataset_id
    assert evaluation_run.status == EvaluationExecutionStatus.SUCCEEDED
    assert evaluation_run.total_cases == 5
    assert evaluation_run.completed_cases == 5
    assert evaluation_run.succeeded_cases == 3
    assert evaluation_run.failed_cases == 1
    assert evaluation_run.timed_out_cases == 1
    assert evaluation_run.started_at is not None
    assert evaluation_run.completed_at is not None

    assert len(case_runs) == 5
    assert all(
        case_run.evaluation_run_id == evaluation_run.evaluation_run_id
        for case_run in case_runs
    )

    stored_artifact = artifact_store.load(
        evaluation_run.evaluation_run_id,
    )

    assert stored_artifact.evaluation_run == evaluation_run
    assert stored_artifact.evaluation_cases == evaluation_cases
    assert stored_artifact.case_runs == case_runs


@pytest.mark.asyncio
async def test_evaluation_run_service_rejects_empty_case_list() -> None:
    dataset = make_dataset()
    batch_case_runner = FakeBatchCaseRunner(statuses=[])
    service = EvaluationRunService(batch_case_runner)

    with pytest.raises(
        ValueError,
        match="requires at least one case",
    ):
        await service.execute(
            dataset=dataset,
            evaluation_cases=[],
            config=make_config(),
        )

    assert batch_case_runner.call_count == 0


@pytest.mark.asyncio
async def test_evaluation_run_service_rejects_cases_from_another_dataset() -> None:
    dataset = make_dataset()
    other_dataset = make_dataset()
    mismatched_case = make_evaluation_cases(other_dataset, 1)
    batch_case_runner = FakeBatchCaseRunner(
        statuses=[EvaluationExecutionStatus.SUCCEEDED],
    )
    service = EvaluationRunService(batch_case_runner)

    with pytest.raises(
        ValueError,
        match="must belong to the supplied dataset",
    ):
        await service.execute(
            dataset=dataset,
            evaluation_cases=mismatched_case,
            config=make_config(),
        )

    assert batch_case_runner.call_count == 0