from __future__ import annotations

from collections.abc import Mapping

from app.schemas.evaluation_entities import (
    CaseRun,
    EvaluationExecutionStatus,
    EvaluationRunArtifact,
)
from app.schemas.llm_judge import LLMJudgeReport, LLMJudgeStatus
from app.schemas.trace_replay import TraceReplay
from app.services.llm_judge_service import LLMJudgeService


class LLMJudgeArtifactService:
    """Attach one LLM Judge report to every CaseRun in an evaluation artifact.

    The maximum call limit applies only to successful target Agent runs that
    would invoke the Judge provider. Cases skipped because their target Agent
    failed do not consume the configured Judge-call budget.
    """

    def __init__(
        self,
        *,
        llm_judge_service: LLMJudgeService,
        max_judge_calls: int,
    ) -> None:
        if max_judge_calls < 0:
            raise ValueError("max_judge_calls must be greater than or equal to 0.")

        self._llm_judge_service = llm_judge_service
        self._max_judge_calls = max_judge_calls

    async def evaluate_artifact(
        self,
        *,
        artifact: EvaluationRunArtifact,
        traces: Mapping[str, TraceReplay],
    ) -> EvaluationRunArtifact:
        """Return an artifact with Judge results without mutating the input.

        Rule evaluations are passed into the Judge as evidence, but the Judge
        never changes them. When the configured call limit is reached, later
        successful cases receive a skipped Judge report with an explicit reason.
        """

        evaluation_cases_by_id = {
            evaluation_case.evaluation_case_id: evaluation_case
            for evaluation_case in artifact.evaluation_cases
        }
        rule_reports_by_case_run_id = {
            report.case_run_id: report for report in artifact.rule_evaluations
        }

        judge_reports: list[LLMJudgeReport] = []
        judge_call_count = 0

        for case_run in artifact.case_runs:
            evaluation_case = evaluation_cases_by_id.get(
                case_run.evaluation_case_id,
            )

            if evaluation_case is None:
                raise ValueError(
                    "CaseRun references an unknown evaluation_case_id: "
                    f"{case_run.evaluation_case_id}",
                )

            trace = self._resolve_trace(
                case_run=case_run,
                traces=traces,
            )
            rule_report = rule_reports_by_case_run_id.get(
                case_run.case_run_id,
            )

            if self._requires_provider_call(case_run):
                if judge_call_count >= self._max_judge_calls:
                    judge_reports.append(
                        self._call_limit_report(
                            case_run=case_run,
                        ),
                    )
                    continue

                judge_call_count += 1

            report = await self._llm_judge_service.judge(
                evaluation_case=evaluation_case,
                case_run=case_run,
                trace=trace,
                rule_report=rule_report,
            )
            judge_reports.append(report)

        return artifact.model_copy(
            update={
                "llm_judge_evaluations": judge_reports,
            },
        )

    @staticmethod
    def _requires_provider_call(case_run: CaseRun) -> bool:
        return (
            case_run.status == EvaluationExecutionStatus.SUCCEEDED
            and case_run.result is not None
            and case_run.result.status == "succeeded"
        )

    @staticmethod
    def _resolve_trace(
        *,
        case_run: CaseRun,
        traces: Mapping[str, TraceReplay],
    ) -> TraceReplay | None:
        trace_id = case_run.trace_id

        if trace_id is None and case_run.result is not None:
            trace_id = case_run.result.trace_id

        return traces.get(trace_id) if trace_id is not None else None

    def _call_limit_report(
        self,
        *,
        case_run: CaseRun,
    ) -> LLMJudgeReport:
        return LLMJudgeReport(
            case_run_id=case_run.case_run_id,
            status=LLMJudgeStatus.SKIPPED,
            error_message=(
                "LLM Judge was skipped because the configured "
                f"max_judge_calls={self._max_judge_calls} limit was reached."
            ),
        )
