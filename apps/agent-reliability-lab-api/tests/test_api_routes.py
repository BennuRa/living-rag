from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient

from app.api.routes import evaluations
from app.main import app
from app.schemas.agent_run_result import AgentRunResult
from app.schemas.agent_task_case import AgentTaskCase
from app.schemas.evaluation_entities import (
    CaseRun,
    EvaluationCase,
    EvaluationExecutionStatus,
    EvaluationRun,
    EvaluationRunArtifact,
)
from app.schemas.run_config import RunConfig
from app.services.run_artifact_store import EvaluationRunArtifactStore


def make_artifact() -> EvaluationRunArtifact:
    dataset_id = uuid4()
    evaluation_run_id = uuid4()
    evaluation_case_id = uuid4()

    evaluation_case = EvaluationCase(
        evaluation_case_id=evaluation_case_id,
        dataset_id=dataset_id,
        task=AgentTaskCase(
            case_id="eligibility-001",
            name="退款资格测试",
            user_input="订单 O2025001 可以退款吗？",
            context={"user_external_id": "USR001"},
            expected_route="refund_eligibility",
            expected_behavior=["返回退款资格结论"],
        ),
    )

    case_run = CaseRun(
        evaluation_run_id=evaluation_run_id,
        evaluation_case_id=evaluation_case_id,
        status=EvaluationExecutionStatus.SUCCEEDED,
        attempt_count=1,
        result=AgentRunResult(
            status="succeeded",
            final_answer="订单符合当前退款条件",
            trace_id="trace-api-001",
            latency_ms=35.5,
        ),
        trace_id="trace-api-001",
        latency_ms=35.5,
    )

    evaluation_run = EvaluationRun(
        evaluation_run_id=evaluation_run_id,
        dataset_id=dataset_id,
        config=RunConfig(workflow_version="0.1.0"),
        status=EvaluationExecutionStatus.SUCCEEDED,
        total_cases=1,
        completed_cases=1,
        succeeded_cases=1,
    )

    return EvaluationRunArtifact(
        evaluation_run=evaluation_run,
        evaluation_cases=[evaluation_case],
        case_runs=[case_run],
    )


def test_read_evaluation_run_from_artifact(
    tmp_path: Path,
    monkeypatch,
) -> None:
    artifact = make_artifact()
    store = EvaluationRunArtifactStore(tmp_path)
    store.save(artifact)

    monkeypatch.setattr(
        evaluations,
        "artifact_store",
        EvaluationRunArtifactStore(tmp_path),
    )

    client = TestClient(app)
    response = client.get(
        f"/api/evaluation-runs/"
        f"{artifact.evaluation_run.evaluation_run_id}",
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["evaluation_run"]["evaluation_run_id"] == str(
        artifact.evaluation_run.evaluation_run_id,
    )
    assert len(payload["case_runs"]) == 1


def test_read_evaluation_run_summary(
    tmp_path: Path,
    monkeypatch,
) -> None:
    artifact = make_artifact()
    store = EvaluationRunArtifactStore(tmp_path)
    store.save(artifact)

    monkeypatch.setattr(
        evaluations,
        "artifact_store",
        EvaluationRunArtifactStore(tmp_path),
    )

    client = TestClient(app)
    response = client.get(
        f"/api/evaluation-runs/"
        f"{artifact.evaluation_run.evaluation_run_id}/summary",
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "succeeded"
    assert payload["total_cases"] == 1
    assert payload["succeeded_cases"] == 1


def test_read_single_evaluation_case(
    tmp_path: Path,
    monkeypatch,
) -> None:
    artifact = make_artifact()
    store = EvaluationRunArtifactStore(tmp_path)
    store.save(artifact)

    monkeypatch.setattr(
        evaluations,
        "artifact_store",
        EvaluationRunArtifactStore(tmp_path),
    )

    case_run = artifact.case_runs[0]
    client = TestClient(app)
    response = client.get(
        f"/api/evaluation-runs/"
        f"{artifact.evaluation_run.evaluation_run_id}/"
        f"cases/{case_run.case_run_id}",
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["evaluation_case"]["task"]["case_id"] == (
        "eligibility-001"
    )
    assert payload["case_run"]["trace_id"] == "trace-api-001"


def test_read_missing_evaluation_run_returns_404(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        evaluations,
        "artifact_store",
        EvaluationRunArtifactStore(tmp_path),
    )

    client = TestClient(app)
    response = client.get(
        f"/api/evaluation-runs/{uuid4()}",
    )

    assert response.status_code == 404
    assert "Evaluation run not found" in response.json()["detail"]


def test_read_missing_case_returns_404(
    tmp_path: Path,
    monkeypatch,
) -> None:
    artifact = make_artifact()
    store = EvaluationRunArtifactStore(tmp_path)
    store.save(artifact)

    monkeypatch.setattr(
        evaluations,
        "artifact_store",
        EvaluationRunArtifactStore(tmp_path),
    )

    client = TestClient(app)
    response = client.get(
        f"/api/evaluation-runs/"
        f"{artifact.evaluation_run.evaluation_run_id}/"
        f"cases/{uuid4()}",
    )

    assert response.status_code == 404
    assert "Case run not found" in response.json()["detail"]


def test_trace_route_rejects_blank_trace_id() -> None:
    client = TestClient(app)

    response = client.get("/api/traces/%20")

    assert response.status_code == 400
    assert response.json()["detail"] == "trace_id must not be blank"


def test_health_route_remains_available() -> None:
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_list_evaluation_runs(
    tmp_path: Path,
    monkeypatch,
) -> None:
    artifact = make_artifact()
    store = EvaluationRunArtifactStore(tmp_path)
    store.save(artifact)

    monkeypatch.setattr(
        evaluations,
        "artifact_store",
        EvaluationRunArtifactStore(tmp_path),
    )

    client = TestClient(app)
    response = client.get("/api/evaluation-runs")

    assert response.status_code == 200
    payload = response.json()

    assert len(payload) == 1
    assert payload[0]["evaluation_run_id"] == str(
        artifact.evaluation_run.evaluation_run_id,
    )
    assert payload[0]["status"] == "succeeded"


def test_list_evaluation_runs_returns_empty_list_for_missing_directory(
    tmp_path: Path,
    monkeypatch,
) -> None:
    artifact_dir = tmp_path / "does-not-exist"

    monkeypatch.setattr(
        evaluations,
        "artifact_store",
        EvaluationRunArtifactStore(artifact_dir),
    )

    client = TestClient(app)
    response = client.get("/api/evaluation-runs")

    assert response.status_code == 200
    assert response.json() == []


def test_list_cases_in_evaluation_run(
    tmp_path: Path,
    monkeypatch,
) -> None:
    artifact = make_artifact()
    store = EvaluationRunArtifactStore(tmp_path)
    store.save(artifact)

    monkeypatch.setattr(
        evaluations,
        "artifact_store",
        EvaluationRunArtifactStore(tmp_path),
    )

    evaluation_run_id = artifact.evaluation_run.evaluation_run_id
    response = TestClient(app).get(
        f"/api/evaluation-runs/{evaluation_run_id}/cases",
    )

    assert response.status_code == 200
    payload = response.json()

    assert len(payload) == 1
    assert payload[0]["evaluation_case"]["task"]["case_id"] == (
        "eligibility-001"
    )
    assert payload[0]["case_run"]["status"] == "succeeded"
    assert payload[0]["case_run"]["trace_id"] == "trace-api-001"


def test_list_cases_for_missing_evaluation_run_returns_404(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        evaluations,
        "artifact_store",
        EvaluationRunArtifactStore(tmp_path),
    )

    response = TestClient(app).get(
        f"/api/evaluation-runs/{uuid4()}/cases",
    )

    assert response.status_code == 404
    assert "Evaluation run not found" in response.json()["detail"]