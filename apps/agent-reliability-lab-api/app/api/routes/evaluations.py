from __future__ import annotations

from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.schemas.evaluation_entities import (
    CaseRun,
    EvaluationCase,
    EvaluationRun,
    EvaluationRunArtifact,
)
from app.services.evaluation_query_service import EvaluationQueryService
from app.services.run_artifact_store import EvaluationRunArtifactStore

PROJECT_ROOT = Path(__file__).resolve().parents[3]
ARTIFACT_DIR = PROJECT_ROOT / "outputs" / "evaluation-runs"

router = APIRouter(
    prefix="/api/evaluation-runs",
    tags=["evaluations"],
)

artifact_store = EvaluationRunArtifactStore(ARTIFACT_DIR)
query_service = EvaluationQueryService()


class EvaluationCaseDetail(BaseModel):
    evaluation_case: EvaluationCase
    case_run: CaseRun


def _load_artifact(evaluation_run_id: UUID) -> EvaluationRunArtifact:
    try:
        return artifact_store.load(evaluation_run_id)
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail=f"Evaluation run not found: {evaluation_run_id}",
        ) from exc


@router.get(
    "",
    response_model=list[EvaluationRun],
    summary="List evaluation runs",
)
async def read_evaluation_runs() -> list[EvaluationRun]:
    artifacts = artifact_store.list_runs()

    return [
        query_service.get_run(artifact)
        for artifact in artifacts
    ]


@router.get(
    "/{evaluation_run_id}",
    response_model=EvaluationRunArtifact,
    summary="Read an evaluation run artifact",
)
async def read_evaluation_run(
    evaluation_run_id: UUID,
) -> EvaluationRunArtifact:
    return _load_artifact(evaluation_run_id)


@router.get(
    "/{evaluation_run_id}/summary",
    response_model=EvaluationRun,
    summary="Read an evaluation run summary",
)
async def read_evaluation_run_summary(
    evaluation_run_id: UUID,
) -> EvaluationRun:
    artifact = _load_artifact(evaluation_run_id)
    return query_service.get_run(artifact)


@router.get(
    "/{evaluation_run_id}/cases",
    response_model=list[EvaluationCaseDetail],
    summary="List cases in an evaluation run",
)
async def read_evaluation_cases(
    evaluation_run_id: UUID,
) -> list[EvaluationCaseDetail]:
    artifact = _load_artifact(evaluation_run_id)

    details: list[EvaluationCaseDetail] = []

    for case_run in artifact.case_runs:
        try:
            evaluation_case, matched_case_run = query_service.get_case(
                artifact,
                case_run.case_run_id,
            )
        except ValueError as exc:
            raise HTTPException(
                status_code=500,
                detail=str(exc),
            ) from exc

        details.append(
            EvaluationCaseDetail(
                evaluation_case=evaluation_case,
                case_run=matched_case_run,
            ),
        )

    return details


@router.get(
    "/{evaluation_run_id}/cases/{case_run_id}",
    response_model=EvaluationCaseDetail,
    summary="Read one case run",
)
async def read_evaluation_case(
    evaluation_run_id: UUID,
    case_run_id: UUID,
) -> EvaluationCaseDetail:
    artifact = _load_artifact(evaluation_run_id)

    try:
        evaluation_case, case_run = query_service.get_case(
            artifact,
            case_run_id,
        )
    except KeyError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=500,
            detail=str(exc),
        ) from exc

    return EvaluationCaseDetail(
        evaluation_case=evaluation_case,
        case_run=case_run,
    )