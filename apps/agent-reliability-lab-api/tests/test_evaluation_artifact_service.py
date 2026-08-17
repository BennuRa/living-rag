from uuid import uuid4

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
from app.schemas.rule_evaluation import (
    RuleCheckName,
    RuleCheckStatus,
)
from app.schemas.run_config import RunConfig
from app.schemas.trace_replay import TraceReplay
from app.services.evaluation_artifact_service import EvaluationArtifactService


def make_artifact() -> EvaluationRunArtifact:
    dataset = EvaluationDataset(
        name="Artifact evaluation dataset",
        source_path="shared/datasets/agent-tasks",
        version="1",
    )

    evaluation_case = EvaluationCase(
        dataset_id=dataset.dataset_id,
        task=AgentTaskCase(
            case_id="artifact-evaluation-001",
            name="Artifact evaluation case",
            user_input="Can order O2025001 be refunded?",
            expected_behavior=["Return a deterministic result."],
            expected_intent="order_membership",
        ),
    )

    run = EvaluationRun(
        dataset_id=dataset.dataset_id,
        config=RunConfig(workflow_version="0.1.0"),
        status=EvaluationExecutionStatus.SUCCEEDED,
        total_cases=1,
        completed_cases=1,
        succeeded_cases=1,
    )

    case_run = CaseRun(
        evaluation_run_id=run.evaluation_run_id,
        evaluation_case_id=evaluation_case.evaluation_case_id,
        status=EvaluationExecutionStatus.SUCCEEDED,
        attempt_count=1,
        trace_id="trace-artifact-001",
        result=AgentRunResult(
            status="succeeded",
            final_answer="The order is eligible for a refund.",
            trace_id="trace-artifact-001",
            latency_ms=25,
        ),
    )

    return EvaluationRunArtifact(
        evaluation_run=run,
        evaluation_cases=[evaluation_case],
        case_runs=[case_run],
    )


def make_trace() -> TraceReplay:
    return TraceReplay(
        trace_id="trace-artifact-001",
        run_status="succeeded",
        intent="order_membership",
        final_answer="The order is eligible for a refund.",
    )


def test_evaluation_artifact_service_attaches_rule_report() -> None:
    artifact = make_artifact()

    evaluated_artifact = EvaluationArtifactService().evaluate_artifact(
        artifact=artifact,
        traces={"trace-artifact-001": make_trace()},
    )

    assert artifact.rule_evaluations == []
    assert len(evaluated_artifact.rule_evaluations) == 1

    report = evaluated_artifact.rule_evaluations[0]

    assert report.case_run_id == artifact.case_runs[0].case_run_id
    assert report.score == 100
    assert report.passed is True
    assert report.release_blocked is False

    trace_id_check = next(
        check
        for check in report.checks
        if check.name == RuleCheckName.TRACE_ID_PRESENT
    )

    assert trace_id_check.status == RuleCheckStatus.PASSED


def test_evaluation_artifact_service_preserves_missing_trace_as_not_evaluated() -> None:
    artifact = make_artifact()

    evaluated_artifact = EvaluationArtifactService().evaluate_artifact(
        artifact=artifact,
        traces={},
    )

    report = evaluated_artifact.rule_evaluations[0]

    intent_check = next(
        check
        for check in report.checks
        if check.name == RuleCheckName.EXPECTED_INTENT
    )

    assert intent_check.status == RuleCheckStatus.NOT_EVALUATED
    assert report.passed is True


def test_evaluation_artifact_service_rejects_unknown_case_reference() -> None:
    artifact = make_artifact()
    artifact.case_runs[0].evaluation_case_id = uuid4()

    try:
        EvaluationArtifactService().evaluate_artifact(
            artifact=artifact,
            traces={},
        )
    except ValueError as exc:
        assert "unknown evaluation_case_id" in str(exc)
    else:
        raise AssertionError(
            "Expected unknown CaseRun reference to raise ValueError",
        )