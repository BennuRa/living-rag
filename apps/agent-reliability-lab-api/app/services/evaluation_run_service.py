from __future__ import annotations

from datetime import UTC, datetime

from app.schemas.evaluation_entities import (
    CaseRun,
    EvaluationCase,
    EvaluationDataset,
    EvaluationExecutionStatus,
    EvaluationRun,
    EvaluationRunArtifact,
)
from app.schemas.fault_injection import FaultInjectionConfig
from app.schemas.run_config import RunConfig
from app.services.batch_runner import BatchCaseRunner
from app.services.run_artifact_store import EvaluationRunArtifactStore


class EvaluationRunService:
    def __init__(
        self,
        batch_case_runner: BatchCaseRunner,
        artifact_store: EvaluationRunArtifactStore | None = None,
    ) -> None:
        self._batch_case_runner = batch_case_runner
        self._artifact_store = artifact_store

    async def execute(
        self,
        dataset: EvaluationDataset,
        evaluation_cases: list[EvaluationCase],
        config: RunConfig,
        fault: FaultInjectionConfig | None = None,
    ) -> tuple[EvaluationRun, list[CaseRun]]:
        if not evaluation_cases:
            raise ValueError("Evaluation run requires at least one case")

        if any(
            evaluation_case.dataset_id != dataset.dataset_id
            for evaluation_case in evaluation_cases
        ):
            raise ValueError(
                "Every evaluation case must belong to the supplied dataset"
            )

        started_at = datetime.now(UTC)
        evaluation_run = EvaluationRun(
            dataset_id=dataset.dataset_id,
            config=config,
            status=EvaluationExecutionStatus.RUNNING,
            total_cases=len(evaluation_cases),
            started_at=started_at,
        )

        case_runs = await self._batch_case_runner.run_cases(
            evaluation_run_id=evaluation_run.evaluation_run_id,
            evaluation_cases=evaluation_cases,
            config=config,
            fault=fault,
        )

        succeeded_cases = sum(
            case_run.status == EvaluationExecutionStatus.SUCCEEDED
            for case_run in case_runs
        )
        failed_cases = sum(
            case_run.status == EvaluationExecutionStatus.FAILED
            for case_run in case_runs
        )
        timed_out_cases = sum(
            case_run.status == EvaluationExecutionStatus.TIMED_OUT
            for case_run in case_runs
        )

        completed_at = datetime.now(UTC)

        completed_run = evaluation_run.model_copy(
            update={
                "status": EvaluationExecutionStatus.SUCCEEDED,
                "completed_cases": len(case_runs),
                "succeeded_cases": succeeded_cases,
                "failed_cases": failed_cases,
                "timed_out_cases": timed_out_cases,
                "completed_at": completed_at,
            }
        )

        if self._artifact_store is not None:
            self._artifact_store.save(
                EvaluationRunArtifact(
                    evaluation_run=completed_run,
                    evaluation_cases=evaluation_cases,
                    case_runs=case_runs,
                )
            )

        return completed_run, case_runs