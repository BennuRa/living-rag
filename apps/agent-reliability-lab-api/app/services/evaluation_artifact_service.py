from __future__ import annotations

from collections.abc import Mapping

from app.schemas.evaluation_entities import (
    EvaluationRunArtifact,
)
from app.schemas.trace_replay import TraceReplay
from app.services.rule_evaluation_service import RuleEvaluationService


class EvaluationArtifactService:
    """Attach deterministic rule reports to one evaluation artifact."""

    def __init__(
        self,
        rule_evaluation_service: RuleEvaluationService | None = None,
    ) -> None:
        self._rule_evaluation_service = (
            rule_evaluation_service or RuleEvaluationService()
        )

    def evaluate_artifact(
        self,
        artifact: EvaluationRunArtifact,
        traces: Mapping[str, TraceReplay],
    ) -> EvaluationRunArtifact:
        """Evaluate every CaseRun and return an updated artifact.

        The input artifact is not mutated. A missing trace is passed as None,
        which makes trace-dependent rules return not_evaluated.
        """

        cases_by_id = {
            evaluation_case.evaluation_case_id: evaluation_case
            for evaluation_case in artifact.evaluation_cases
        }

        reports = []

        for case_run in artifact.case_runs:
            evaluation_case = cases_by_id.get(
                case_run.evaluation_case_id,
            )

            if evaluation_case is None:
                raise ValueError(
                    "CaseRun references an unknown evaluation_case_id: "
                    f"{case_run.evaluation_case_id}",
                )

            trace_id = case_run.trace_id

            if trace_id is None and case_run.result is not None:
                trace_id = case_run.result.trace_id

            trace = traces.get(trace_id) if trace_id is not None else None

            reports.append(
                self._rule_evaluation_service.evaluate(
                    evaluation_case=evaluation_case,
                    case_run=case_run,
                    trace=trace,
                ),
            )

        return artifact.model_copy(
            update={
                "rule_evaluations": reports,
            },
        )