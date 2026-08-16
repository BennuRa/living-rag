from __future__ import annotations

from uuid import uuid4

import pytest

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
from app.services.evaluation_query_service import EvaluationQueryService


def make_artifact() -> EvaluationRunArtifact:
    dataset_id = uuid4()
    evaluation_run_id = uuid4()
    evaluation_case_id = uuid4()

    task = AgentTaskCase(
        case_id="eligibility-001",
        name="退款资格测试",
        user_input="订单 O2025001 可以退款吗？",
        context={"user_external_id": "USR001"},
        expected_route="refund_eligibility",
        expected_behavior=["返回退款资格结论"],
    )

    evaluation_case = EvaluationCase(
        evaluation_case_id=evaluation_case_id,
        dataset_id=dataset_id,
        task=task,
    )

    case_run = CaseRun(
        evaluation_run_id=evaluation_run_id,
        evaluation_case_id=evaluation_case_id,
        status=EvaluationExecutionStatus.SUCCEEDED,
        attempt_count=1,
        result=AgentRunResult(
            status="succeeded",
            final_answer="订单符合当前退款条件",
            trace_id="trace-001",
            latency_ms=35.5,
        ),
        trace_id="trace-001",
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


def test_query_service_returns_run_and_collections() -> None:
    artifact = make_artifact()
    service = EvaluationQueryService()

    assert (
        service.get_run(artifact).evaluation_run_id
        == artifact.evaluation_run.evaluation_run_id
    )
    assert service.get_cases(artifact) == artifact.evaluation_cases
    assert service.get_case_runs(artifact) == artifact.case_runs


def test_query_service_returns_case_and_case_run() -> None:
    artifact = make_artifact()
    service = EvaluationQueryService()

    case_run_id = artifact.case_runs[0].case_run_id
    evaluation_case, case_run = service.get_case(
        artifact,
        case_run_id,
    )

    assert evaluation_case.evaluation_case_id == (
        artifact.evaluation_cases[0].evaluation_case_id
    )
    assert case_run.case_run_id == case_run_id
    assert case_run.trace_id == "trace-001"


def test_query_service_finds_case_by_trace_id() -> None:
    artifact = make_artifact()
    service = EvaluationQueryService()

    evaluation_case, case_run = service.get_case_by_trace_id(
        artifact,
        " trace-001 ",
    )

    assert evaluation_case.task.case_id == "eligibility-001"
    assert case_run.trace_id == "trace-001"


def test_query_service_rejects_unknown_case_run() -> None:
    artifact = make_artifact()
    service = EvaluationQueryService()

    with pytest.raises(KeyError, match="Case run not found"):
        service.get_case(
            artifact,
            uuid4(),
        )


def test_query_service_rejects_unknown_trace_id() -> None:
    artifact = make_artifact()
    service = EvaluationQueryService()

    with pytest.raises(
        KeyError,
        match="Case run not found for trace_id",
    ):
        service.get_case_by_trace_id(
            artifact,
            "trace-does-not-exist",
        )


def test_query_service_rejects_blank_trace_id() -> None:
    artifact = make_artifact()
    service = EvaluationQueryService()

    with pytest.raises(ValueError, match="trace_id must not be blank"):
        service.get_case_by_trace_id(
            artifact,
            "  ",
        )


def test_query_service_rejects_inconsistent_artifact() -> None:
    artifact = make_artifact()
    artifact.case_runs[0].evaluation_case_id = uuid4()
    service = EvaluationQueryService()

    with pytest.raises(
        ValueError,
        match="evaluation case .* is missing",
    ):
        service.get_case(
            artifact,
            artifact.case_runs[0].case_run_id,
        )