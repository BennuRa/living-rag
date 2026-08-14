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