from __future__ import annotations

from uuid import UUID

from app.schemas.evaluation_entities import (
    CaseRun,
    EvaluationCase,
    EvaluationRun,
    EvaluationRunArtifact,
)


class EvaluationQueryService:
    """Read evaluation run artifacts for API and frontend consumers."""

    def get_run(
        self,
        artifact: EvaluationRunArtifact,
    ) -> EvaluationRun:
        return artifact.evaluation_run

    def get_cases(
        self,
        artifact: EvaluationRunArtifact,
    ) -> list[EvaluationCase]:
        return artifact.evaluation_cases

    def get_case_runs(
        self,
        artifact: EvaluationRunArtifact,
    ) -> list[CaseRun]:
        return artifact.case_runs

    def get_case(
        self,
        artifact: EvaluationRunArtifact,
        case_run_id: UUID,
    ) -> tuple[EvaluationCase, CaseRun]:
        case_run = next(
            (
                item
                for item in artifact.case_runs
                if item.case_run_id == case_run_id
            ),
            None,
        )
        if case_run is None:
            raise KeyError(
                f"Case run not found: {case_run_id}",
            )

        evaluation_case = next(
            (
                item
                for item in artifact.evaluation_cases
                if item.evaluation_case_id
                == case_run.evaluation_case_id
            ),
            None,
        )
        if evaluation_case is None:
            raise ValueError(
                "Artifact is inconsistent: evaluation case "
                f"{case_run.evaluation_case_id} is missing",
            )

        return evaluation_case, case_run

    def get_case_by_trace_id(
        self,
        artifact: EvaluationRunArtifact,
        trace_id: str,
    ) -> tuple[EvaluationCase, CaseRun]:
        normalized_trace_id = trace_id.strip()
        if not normalized_trace_id:
            raise ValueError("trace_id must not be blank")

        case_run = next(
            (
                item
                for item in artifact.case_runs
                if item.trace_id == normalized_trace_id
            ),
            None,
        )
        if case_run is None:
            raise KeyError(
                f"Case run not found for trace_id: {normalized_trace_id}",
            )

        return self.get_case(
            artifact,
            case_run.case_run_id,
        )