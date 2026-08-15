from __future__ import annotations

import asyncio
from uuid import UUID

from app.schemas.evaluation_entities import CaseRun, EvaluationCase
from app.schemas.fault_injection import FaultInjectionConfig
from app.schemas.run_config import RunConfig
from app.services.case_runner import CaseRunner


class BatchCaseRunner:
    def __init__(self, case_runner: CaseRunner) -> None:
        self._case_runner = case_runner

    async def run_cases(
        self,
        evaluation_run_id: UUID,
        evaluation_cases: list[EvaluationCase],
        config: RunConfig,
        fault: FaultInjectionConfig | None = None,
    ) -> list[CaseRun]:
        semaphore = asyncio.Semaphore(config.max_concurrency)

        async def run_one(evaluation_case: EvaluationCase) -> CaseRun:
            async with semaphore:
                return await self._case_runner.run_case(
                    evaluation_run_id=evaluation_run_id,
                    evaluation_case=evaluation_case,
                    config=config,
                    fault=fault,
                )

        return list(
            await asyncio.gather(
                *(
                    run_one(evaluation_case)
                    for evaluation_case in evaluation_cases
                )
            )
        )