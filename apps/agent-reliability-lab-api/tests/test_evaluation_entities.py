from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas.agent_run_result import AgentRunResult
from app.schemas.agent_task_case import AgentTaskCase
from app.schemas.evaluation_entities import (
    CaseRun,
    Evaluation,
    EvaluationCase,
    EvaluationDataset,
    EvaluationExecutionStatus,
    EvaluationRun,
    FaultInjectionRun,
)
from app.schemas.fault_injection import (
    FaultInjectionConfig,
    FaultInjectionType,
)
from app.schemas.run_config import RunConfig


def make_task() -> AgentTaskCase:
    return AgentTaskCase(
        case_id="evaluation-entity-task",
        name="Evaluation entity test task",
        user_input="Can order O2025001 be refunded?",
        context={"user_external_id": "USR001"},
        expected_behavior=["Return a deterministic eligibility result"],
    )


def test_evaluation_dataset_creates_stable_metadata() -> None:
    dataset = EvaluationDataset(
        name="Agent tasks",
        source_path="shared/datasets/agent-tasks",
        version="v1",
    )

    assert dataset.dataset_id is not None
    assert dataset.imported_at.tzinfo is not None


def test_evaluation_case_links_task_to_dataset() -> None:
    dataset_id = uuid4()

    evaluation_case = EvaluationCase(
        dataset_id=dataset_id,
        task=make_task(),
    )

    assert evaluation_case.dataset_id == dataset_id
    assert evaluation_case.task.case_id == "evaluation-entity-task"


def test_evaluation_run_keeps_dataset_and_config_snapshot() -> None:
    dataset_id = uuid4()
    config = RunConfig(
        workflow_version="0.1.0",
        timeout_seconds=30,
    )

    evaluation_run = EvaluationRun(
        dataset_id=dataset_id,
        config=config,
    )

    assert evaluation_run.dataset_id == dataset_id
    assert evaluation_run.config.workflow_version == "0.1.0"
    assert evaluation_run.status == EvaluationExecutionStatus.PENDING


def test_case_run_and_evaluation_link_execution_to_score() -> None:
    case_run = CaseRun(
        evaluation_run_id=uuid4(),
        evaluation_case_id=uuid4(),
        status=EvaluationExecutionStatus.SUCCEEDED,
        result=AgentRunResult(
            status="succeeded",
            final_answer="The order is eligible for a refund.",
            latency_ms=25,
        ),
    )

    evaluation = Evaluation(
        case_run_id=case_run.case_run_id,
        evaluator_name="deterministic_rules",
        status=EvaluationExecutionStatus.SUCCEEDED,
        score=100,
        passed=True,
        reason="All deterministic checks passed.",
    )

    assert case_run.result is not None
    assert evaluation.case_run_id == case_run.case_run_id
    assert evaluation.score == 100
    assert evaluation.passed is True


def test_fault_injection_run_rejects_unexpected_fields() -> None:
    with pytest.raises(ValidationError):
        FaultInjectionRun(
            case_run_id=uuid4(),
            fault=FaultInjectionConfig(
                enabled=True,
                fault_type=FaultInjectionType.TOOL_TIMEOUT,
                target_tool="get_order",
            ),
            unexpected_field="not allowed",
        )


def test_evaluation_run_records_case_counts() -> None:
    config = RunConfig(workflow_version="0.1.0")

    run = EvaluationRun(
        dataset_id=uuid4(),
        config=config,
        status=EvaluationExecutionStatus.RUNNING,
        total_cases=20,
        completed_cases=7,
        succeeded_cases=5,
        failed_cases=1,
        timed_out_cases=1,
    )

    assert run.status == EvaluationExecutionStatus.RUNNING
    assert run.total_cases == 20
    assert run.completed_cases == 7
    assert run.succeeded_cases == 5
    assert run.failed_cases == 1
    assert run.timed_out_cases == 1


def test_case_run_records_execution_metadata() -> None:
    run_id = uuid4()
    case_id = uuid4()

    case_run = CaseRun(
        evaluation_run_id=run_id,
        evaluation_case_id=case_id,
        status=EvaluationExecutionStatus.SUCCEEDED,
        attempt_count=1,
        trace_id="trace-demo",
        latency_ms=125.5,
        token_usage={
            "prompt_tokens": 120,
            "completion_tokens": 80,
            "total_tokens": 200,
        },
        estimated_cost=0.01,
    )

    assert case_run.status == EvaluationExecutionStatus.SUCCEEDED
    assert case_run.attempt_count == 1
    assert case_run.trace_id == "trace-demo"
    assert case_run.latency_ms == 125.5
    assert case_run.token_usage == {
        "prompt_tokens": 120,
        "completion_tokens": 80,
        "total_tokens": 200,
    }
    assert case_run.estimated_cost == 0.01


def test_case_run_supports_timeout_status_and_error() -> None:
    case_run = CaseRun(
        evaluation_run_id=uuid4(),
        evaluation_case_id=uuid4(),
        status=EvaluationExecutionStatus.TIMED_OUT,
        attempt_count=2,
        latency_ms=30000,
        error_message="request timed out",
    )

    assert case_run.status == EvaluationExecutionStatus.TIMED_OUT
    assert case_run.attempt_count == 2
    assert case_run.error_message == "request timed out"


@pytest.mark.parametrize(
    ("field_name", "invalid_value"),
    [
        ("total_cases", -1),
        ("completed_cases", -1),
        ("succeeded_cases", -1),
        ("failed_cases", -1),
    ],
)
def test_evaluation_run_rejects_negative_counts(
    field_name: str,
    invalid_value: int,
) -> None:
    with pytest.raises(ValidationError) as exc_info:
        EvaluationRun(
            dataset_id=uuid4(),
            config=RunConfig(workflow_version="0.1.0"),
            **{field_name: invalid_value},
        )

    assert field_name in str(exc_info.value)


@pytest.mark.parametrize(
    ("field_name", "invalid_value"),
    [
        ("attempt_count", -1),
        ("latency_ms", -0.01),
        ("estimated_cost", -0.01),
    ],
)
def test_case_run_rejects_negative_execution_values(
    field_name: str,
    invalid_value: float,
) -> None:
    with pytest.raises(ValidationError) as exc_info:
        CaseRun(
            evaluation_run_id=uuid4(),
            evaluation_case_id=uuid4(),
            **{field_name: invalid_value},
        )

    assert field_name in str(exc_info.value)


def test_evaluation_entities_use_pending_as_default_status() -> None:
    run = EvaluationRun(
        dataset_id=uuid4(),
        config=RunConfig(workflow_version="0.1.0"),
    )
    case_run = CaseRun(
        evaluation_run_id=run.evaluation_run_id,
        evaluation_case_id=uuid4(),
    )

    assert run.status == EvaluationExecutionStatus.PENDING
    assert case_run.status == EvaluationExecutionStatus.PENDING
    assert case_run.attempt_count == 0
    assert case_run.trace_id is None
    assert case_run.result is None