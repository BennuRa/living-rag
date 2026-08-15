from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas.agent_run_result import AgentRunResult
from app.schemas.agent_task_case import AgentTaskCase
from app.schemas.evaluation_entities import (
    CaseRun,
    EvaluationCase,
    EvaluationDataset,
    EvaluationExecutionStatus,
    EvaluationRun,
    EvaluationRunArtifact,
)
from app.schemas.run_config import RunConfig
from app.services.run_artifact_store import EvaluationRunArtifactStore


def make_artifact() -> EvaluationRunArtifact:
    dataset = EvaluationDataset(
        name="artifact-test-dataset",
        source_path="tests/data/artifact-test.jsonl",
        version="1",
    )
    evaluation_case = EvaluationCase(
        dataset_id=dataset.dataset_id,
        task=AgentTaskCase(
            case_id="artifact-case-001",
            name="Artifact 保存测试",
            user_input="请验证保存结果。",
            expected_route="policy_qa",
            expected_behavior=["保存并恢复评测结果"],
        ),
    )
    evaluation_run = EvaluationRun(
        dataset_id=dataset.dataset_id,
        config=RunConfig(workflow_version="0.1.0"),
        status=EvaluationExecutionStatus.SUCCEEDED,
        total_cases=1,
        completed_cases=1,
        succeeded_cases=1,
        failed_cases=0,
        timed_out_cases=0,
        started_at=datetime(
            2026,
            1,
            1,
            10,
            0,
            0,
            tzinfo=UTC,
        ),
        completed_at=datetime(
            2026,
            1,
            1,
            10,
            0,
            12,
            tzinfo=UTC,
        ),
    )
    case_run = CaseRun(
        evaluation_run_id=evaluation_run.evaluation_run_id,
        evaluation_case_id=evaluation_case.evaluation_case_id,
        status=EvaluationExecutionStatus.SUCCEEDED,
        attempt_count=1,
        result=AgentRunResult(
            status="succeeded",
            final_answer="保存测试成功。",
            trace_id="trace-artifact-001",
            latency_ms=12.5,
        ),
        trace_id="trace-artifact-001",
        latency_ms=12.5,
    )

    return EvaluationRunArtifact(
        evaluation_run=evaluation_run,
        evaluation_cases=[evaluation_case],
        case_runs=[case_run],
    )


def test_artifact_store_saves_and_loads_complete_run(
    tmp_path: Path,
) -> None:
    artifact = make_artifact()
    store = EvaluationRunArtifactStore(
        tmp_path / "evaluation-runs",
    )

    artifact_path = store.save(artifact)
    loaded_artifact = store.load(
        artifact.evaluation_run.evaluation_run_id,
    )

    assert artifact_path.is_file()
    assert artifact_path.name == (
        f"{artifact.evaluation_run.evaluation_run_id}.json"
    )
    assert loaded_artifact == artifact
    assert (
        loaded_artifact.evaluation_run.evaluation_run_id
        == artifact.evaluation_run.evaluation_run_id
    )
    assert loaded_artifact.evaluation_cases[0].task.case_id == (
        "artifact-case-001"
    )
    assert loaded_artifact.case_runs[0].trace_id == "trace-artifact-001"
    assert loaded_artifact.case_runs[0].latency_ms == 12.5


def test_artifact_store_writes_json_compatible_uuid_and_datetime(
    tmp_path: Path,
) -> None:
    artifact = make_artifact()
    store = EvaluationRunArtifactStore(tmp_path)

    artifact_path = store.save(artifact)
    payload = json.loads(
        artifact_path.read_text(encoding="utf-8"),
    )

    run_payload = payload["evaluation_run"]

    assert isinstance(run_payload["evaluation_run_id"], str)
    assert isinstance(run_payload["started_at"], str)
    assert payload["evaluation_cases"][0]["dataset_id"] == str(
        artifact.evaluation_cases[0].dataset_id
    )


def test_artifact_store_rejects_missing_artifact(
    tmp_path: Path,
) -> None:
    store = EvaluationRunArtifactStore(tmp_path)

    with pytest.raises(
        FileNotFoundError,
        match="Evaluation run artifact not found",
    ):
        store.load(uuid4())


def test_artifact_store_rejects_invalid_json(
    tmp_path: Path,
) -> None:
    run_id = uuid4()
    invalid_path = tmp_path / f"{run_id}.json"
    invalid_path.write_text(
        "{this is not valid json",
        encoding="utf-8",
    )
    store = EvaluationRunArtifactStore(tmp_path)

    with pytest.raises(json.JSONDecodeError):
        store.load(run_id)


def test_artifact_store_rejects_invalid_artifact_schema(
    tmp_path: Path,
) -> None:
    run_id = uuid4()
    invalid_path = tmp_path / f"{run_id}.json"
    invalid_path.write_text(
        json.dumps(
            {
                "evaluation_run": {},
                "evaluation_cases": [],
                "case_runs": [],
            }
        ),
        encoding="utf-8",
    )
    store = EvaluationRunArtifactStore(tmp_path)

    with pytest.raises(ValidationError):
        store.load(run_id)