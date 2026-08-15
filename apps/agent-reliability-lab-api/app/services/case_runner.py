from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from uuid import UUID

from app.adapters.target_agent import TargetAgentAdapter
from app.schemas.agent_run_result import AgentRunResult
from app.schemas.evaluation_entities import (
    CaseRun,
    EvaluationCase,
    EvaluationExecutionStatus,
)
from app.schemas.fault_injection import FaultInjectionConfig
from app.schemas.run_config import RunConfig


class CaseRunner:
    def __init__(self, adapter: TargetAgentAdapter) -> None:
        self._adapter = adapter

    async def run_case(
        self,
        evaluation_run_id: UUID,
        evaluation_case: EvaluationCase,
        config: RunConfig,
        fault: FaultInjectionConfig | None = None,
    ) -> CaseRun:
        started_at = datetime.now(UTC)
        max_attempts = config.max_retries + 1
        last_result: AgentRunResult | None = None
        last_status = EvaluationExecutionStatus.FAILED
        last_error_message: str | None = None

        for attempt_count in range(1, max_attempts + 1):
            try:
                async with asyncio.timeout(config.timeout_seconds):
                    result = await self._adapter.run(
                        task=evaluation_case.task,
                        config=config,
                        fault=fault,
                    )
            except TimeoutError:
                last_status = EvaluationExecutionStatus.TIMED_OUT
                last_error_message = (
                    "Case execution exceeded "
                    f"{config.timeout_seconds} seconds"
                )
                continue
            except Exception as exc:  # noqa: BLE001
                last_status = EvaluationExecutionStatus.FAILED
                last_error_message = f"{type(exc).__name__}: {exc}"
                continue

            if result.status != "timed_out":
                return CaseRun(
                    evaluation_run_id=evaluation_run_id,
                    evaluation_case_id=evaluation_case.evaluation_case_id,
                    status=EvaluationExecutionStatus(result.status),
                    attempt_count=attempt_count,
                    result=result,
                    trace_id=result.trace_id,
                    latency_ms=result.latency_ms,
                    error_message=result.error_message,
                    started_at=started_at,
                    completed_at=datetime.now(UTC),
                )

            last_result = result
            last_status = EvaluationExecutionStatus.TIMED_OUT
            last_error_message = result.error_message

        return CaseRun(
            evaluation_run_id=evaluation_run_id,
            evaluation_case_id=evaluation_case.evaluation_case_id,
            status=last_status,
            attempt_count=max_attempts,
            result=last_result,
            trace_id=last_result.trace_id if last_result is not None else None,
            latency_ms=last_result.latency_ms if last_result is not None else None,
            error_message=last_error_message,
            started_at=started_at,
            completed_at=datetime.now(UTC),
        )