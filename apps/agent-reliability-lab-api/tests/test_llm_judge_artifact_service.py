from __future__ import annotations

import json
from uuid import UUID, uuid4

import pytest

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
from app.schemas.llm_judge import LLMJudgeStatus
from app.schemas.rule_evaluation import (
    RuleCheck,
    RuleCheckName,
    RuleCheckStatus,
    RuleEvaluationReport,
)
from app.schemas.run_config import RunConfig
from app.schemas.trace_replay import TraceReplay
from app.services.llm_judge_artifact_service import (
    LLMJudgeArtifactService,
)
from app.services.llm_judge_client import LLMJudgeClient
from app.services.llm_judge_service import LLMJudgeService


class FakeJudgeClient:
    """A deterministic Judge client used by artifact-service tests."""

    def __init__(self, response: str) -> None:
        self.response = response
        self.calls: list[dict[str, str]] = []

    async def complete(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        model_name: str,
    ) -> str:
        self.calls.append(
            {
                "system_prompt": system_prompt,
                "user_prompt": user_prompt,
                "model_name": model_name,
            },
        )
        return self.response


def successful_judge_response() -> str:
    return json.dumps(
        {
            "overall_score": 88,
            "passed": True,
            "conclusion_correctness": {
                "score": 4,
                "reason": "The conclusion follows the supplied evidence.",
            },
            "answer_completeness": {
                "score": 4,
                "reason": "The answer includes the required limitations.",
            },
            "citation_support": {
                "score": 4,
                "reason": "The available citations support the conclusion.",
            },
            "conflict_handling": {
                "score": 4,
                "reason": "No unresolved conflict appears in this case.",
            },
            "safety": {
                "score": 5,
                "reason": "The answer avoids unsupported claims.",
            },
            "evidence_basedness": {
                "score": 4,
                "reason": "The answer states evidence limitations.",
            },
            "reasoning": (
                "The response is safe and evidence-based, with minor room for additional detail."
            ),
        },
    )


def make_task(case_id: str) -> AgentTaskCase:
    return AgentTaskCase(
        case_id=case_id,
        name=f"Generic evaluation task {case_id}",
        user_input="Summarize the evidence and state any limitations.",
        expected_behavior=[
            "Use available evidence.",
            "State limitations when evidence is incomplete.",
        ],
        forbidden_behavior=[
            "Invent unsupported facts.",
        ],
        failure_conditions=[
            "States unsupported conclusions as certain.",
        ],
        tags=["generic"],
    )


def make_case_run(
    *,
    evaluation_run_id: UUID,
    evaluation_case_id: UUID,
    case_id: str,
    succeeded: bool = True,
) -> CaseRun:
    trace_id = f"trace-{case_id}"

    if succeeded:
        result = AgentRunResult(
            status="succeeded",
            final_answer=(
                "The evidence supports a limited conclusion. Further verification is required."
            ),
            trace_id=trace_id,
            latency_ms=25,
        )
        status = EvaluationExecutionStatus.SUCCEEDED
        error_message = None
    else:
        result = AgentRunResult(
            status="failed",
            error_message="Simulated target Agent failure.",
            latency_ms=25,
        )
        status = EvaluationExecutionStatus.FAILED
        error_message = "Simulated target Agent failure."

    return CaseRun(
        evaluation_run_id=evaluation_run_id,
        evaluation_case_id=evaluation_case_id,
        status=status,
        result=result,
        trace_id=trace_id if succeeded else None,
        latency_ms=25,
        error_message=error_message,
    )


def make_rule_report(case_run_id: UUID) -> RuleEvaluationReport:
    return RuleEvaluationReport(
        case_run_id=case_run_id,
        checks=[
            RuleCheck(
                name=RuleCheckName.RUN_SUCCEEDED,
                status=RuleCheckStatus.PASSED,
                reason="Target Agent run succeeded.",
            ),
        ],
        score=100,
        passed=True,
        release_blocked=False,
        evaluated_check_count=1,
        passed_check_count=1,
        failed_check_count=0,
        not_evaluated_check_count=0,
    )


def make_artifact(
    *,
    succeeded_cases: list[bool],
) -> tuple[EvaluationRunArtifact, dict[str, TraceReplay]]:
    dataset_id = uuid4()
    evaluation_run = EvaluationRun(
        dataset_id=dataset_id,
        config=RunConfig(workflow_version="1.0.0"),
        status=EvaluationExecutionStatus.SUCCEEDED,
        total_cases=len(succeeded_cases),
        completed_cases=len(succeeded_cases),
        succeeded_cases=sum(succeeded_cases),
        failed_cases=len(succeeded_cases) - sum(succeeded_cases),
    )
    dataset = EvaluationDataset(
        dataset_id=dataset_id,
        name="generic-evaluation-dataset",
        source_path="tests",
        version="1",
    )

    evaluation_cases: list[EvaluationCase] = []
    case_runs: list[CaseRun] = []
    rule_reports: list[RuleEvaluationReport] = []
    traces: dict[str, TraceReplay] = {}

    for index, succeeded in enumerate(succeeded_cases, start=1):
        case_id = f"case-{index:03d}"
        evaluation_case = EvaluationCase(
            dataset_id=dataset.dataset_id,
            task=make_task(case_id),
        )
        case_run = make_case_run(
            evaluation_run_id=evaluation_run.evaluation_run_id,
            evaluation_case_id=evaluation_case.evaluation_case_id,
            case_id=case_id,
            succeeded=succeeded,
        )

        evaluation_cases.append(evaluation_case)
        case_runs.append(case_run)
        rule_reports.append(make_rule_report(case_run.case_run_id))

        if case_run.trace_id is not None:
            traces[case_run.trace_id] = TraceReplay(
                trace_id=case_run.trace_id,
                run_status="succeeded",
                intent="generic_analysis",
                final_answer=(
                    "The evidence supports a limited conclusion. Further verification is required."
                ),
            )

    artifact = EvaluationRunArtifact(
        evaluation_run=evaluation_run,
        evaluation_cases=evaluation_cases,
        case_runs=case_runs,
        rule_evaluations=rule_reports,
    )

    return artifact, traces


def make_judge_service(
    client: FakeJudgeClient,
) -> LLMJudgeService:
    return LLMJudgeService(
        client=client,
        model_name="fake-judge-model",
    )


@pytest.mark.asyncio
async def test_service_attaches_judge_report_to_each_successful_case() -> None:
    artifact, traces = make_artifact(succeeded_cases=[True, True])
    client = FakeJudgeClient(response=successful_judge_response())

    updated_artifact = await LLMJudgeArtifactService(
        llm_judge_service=make_judge_service(client),
        max_judge_calls=2,
    ).evaluate_artifact(
        artifact=artifact,
        traces=traces,
    )

    assert artifact.llm_judge_evaluations == []
    assert updated_artifact.rule_evaluations == artifact.rule_evaluations
    assert len(updated_artifact.llm_judge_evaluations) == 2
    assert all(
        report.status == LLMJudgeStatus.SUCCEEDED
        for report in updated_artifact.llm_judge_evaluations
    )
    assert len(client.calls) == 2


@pytest.mark.asyncio
async def test_service_skips_later_successful_cases_when_call_limit_is_reached() -> None:
    artifact, traces = make_artifact(succeeded_cases=[True, True])
    client = FakeJudgeClient(response=successful_judge_response())

    updated_artifact = await LLMJudgeArtifactService(
        llm_judge_service=make_judge_service(client),
        max_judge_calls=1,
    ).evaluate_artifact(
        artifact=artifact,
        traces=traces,
    )

    first_report, second_report = updated_artifact.llm_judge_evaluations

    assert first_report.status == LLMJudgeStatus.SUCCEEDED
    assert second_report.status == LLMJudgeStatus.SKIPPED
    assert second_report.error_message is not None
    assert "max_judge_calls=1" in second_report.error_message
    assert len(client.calls) == 1


@pytest.mark.asyncio
async def test_failed_target_agent_case_does_not_consume_judge_call_budget() -> None:
    artifact, traces = make_artifact(succeeded_cases=[False, True])
    client = FakeJudgeClient(response=successful_judge_response())

    updated_artifact = await LLMJudgeArtifactService(
        llm_judge_service=make_judge_service(client),
        max_judge_calls=1,
    ).evaluate_artifact(
        artifact=artifact,
        traces=traces,
    )

    failed_target_report, successful_target_report = updated_artifact.llm_judge_evaluations

    assert failed_target_report.status == LLMJudgeStatus.SKIPPED
    assert successful_target_report.status == LLMJudgeStatus.SUCCEEDED
    assert len(client.calls) == 1


@pytest.mark.asyncio
async def test_service_rejects_case_run_that_references_unknown_evaluation_case() -> None:
    artifact, traces = make_artifact(succeeded_cases=[True])
    artifact_with_missing_case = artifact.model_copy(
        update={"evaluation_cases": []},
    )
    client = FakeJudgeClient(response=successful_judge_response())

    service = LLMJudgeArtifactService(
        llm_judge_service=make_judge_service(client),
        max_judge_calls=1,
    )

    with pytest.raises(ValueError, match="unknown evaluation_case_id"):
        await service.evaluate_artifact(
            artifact=artifact_with_missing_case,
            traces=traces,
        )


def test_service_rejects_negative_judge_call_limit() -> None:
    client = FakeJudgeClient(response=successful_judge_response())

    with pytest.raises(ValueError, match="max_judge_calls"):
        LLMJudgeArtifactService(
            llm_judge_service=make_judge_service(client),
            max_judge_calls=-1,
        )


def test_fake_judge_client_matches_provider_protocol() -> None:
    client: LLMJudgeClient = FakeJudgeClient(
        response=successful_judge_response(),
    )

    assert client is not None
