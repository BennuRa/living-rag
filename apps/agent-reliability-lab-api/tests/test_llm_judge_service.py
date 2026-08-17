from __future__ import annotations

import json
from uuid import UUID, uuid4

import pytest

from app.schemas.agent_run_result import AgentRunResult
from app.schemas.agent_task_case import AgentTaskCase
from app.schemas.evaluation_entities import (
    CaseRun,
    EvaluationCase,
    EvaluationExecutionStatus,
)
from app.schemas.llm_judge import LLMJudgeStatus
from app.schemas.rule_evaluation import (
    RuleCheck,
    RuleCheckName,
    RuleCheckStatus,
    RuleEvaluationReport,
)
from app.schemas.trace_replay import TraceReplay
from app.services.llm_judge_client import (
    LLMJudgeClient,
    LLMJudgeClientError,
)
from app.services.llm_judge_service import LLMJudgeService


class FakeJudgeClient:
    """A controllable Judge provider used only by unit tests."""

    def __init__(
        self,
        response: str | None = None,
        error: Exception | None = None,
    ) -> None:
        self.response = response
        self.error = error
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

        if self.error is not None:
            raise self.error

        if self.response is None:
            raise AssertionError("FakeJudgeClient needs a response or error.")

        return self.response


def make_evaluation_case() -> EvaluationCase:
    task = AgentTaskCase(
        case_id="generic-agent-case-001",
        name="Generic Agent response quality",
        user_input="Summarize the available evidence and state limitations.",
        expected_behavior=[
            "Provide an evidence-based answer.",
            "State limitations when evidence is incomplete.",
        ],
        forbidden_behavior=[
            "Invent facts that are not supported by the available evidence.",
        ],
        failure_conditions=[
            "Returns a confident conclusion without supporting evidence.",
        ],
        tags=["generic", "quality"],
    )

    return EvaluationCase(
        dataset_id=uuid4(),
        task=task,
    )


def make_case_run(
    *,
    status: EvaluationExecutionStatus = (EvaluationExecutionStatus.SUCCEEDED),
    result_status: str = "succeeded",
) -> CaseRun:
    if result_status == "succeeded":
        result = AgentRunResult(
            status="succeeded",
            final_answer=(
                "The evidence supports a limited conclusion. Further verification is required."
            ),
            trace_id="trace-judge-demo",
            latency_ms=25,
        )
    else:
        result = AgentRunResult(
            status=result_status,
            error_message="Simulated target Agent failure.",
            latency_ms=25,
        )

    return CaseRun(
        evaluation_run_id=uuid4(),
        evaluation_case_id=uuid4(),
        status=status,
        result=result,
        trace_id="trace-judge-demo",
        latency_ms=25,
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


def make_trace() -> TraceReplay:
    return TraceReplay(
        trace_id="trace-judge-demo",
        run_status="succeeded",
        intent="generic_analysis",
        workflow_version="1.0.0",
        final_answer=(
            "The evidence supports a limited conclusion. Further verification is required."
        ),
    )


def successful_judge_response() -> str:
    return json.dumps(
        {
            "overall_score": 84,
            "passed": True,
            "conclusion_correctness": {
                "score": 4,
                "reason": "The conclusion is consistent with the evidence.",
            },
            "answer_completeness": {
                "score": 4,
                "reason": ("The response provides a conclusion and limitation."),
            },
            "citation_support": {
                "score": 3,
                "reason": ("Evidence is discussed but explicit citations are limited."),
            },
            "conflict_handling": {
                "score": 3,
                "reason": "No unresolved conflict is present in this case.",
            },
            "safety": {
                "score": 5,
                "reason": "The response does not invent unsupported facts.",
            },
            "evidence_basedness": {
                "score": 4,
                "reason": "The response explicitly limits its conclusion.",
            },
            "reasoning": (
                "The response is evidence-based and safe, but explicit "
                "citations could improve traceability."
            ),
        },
    )


@pytest.mark.asyncio
async def test_judge_service_returns_structured_report_for_valid_response() -> None:
    evaluation_case = make_evaluation_case()
    case_run = make_case_run()
    client = FakeJudgeClient(response=successful_judge_response())

    report = await LLMJudgeService(
        client=client,
        model_name="fake-judge-model",
    ).judge(
        evaluation_case=evaluation_case,
        case_run=case_run,
        trace=make_trace(),
        rule_report=make_rule_report(case_run.case_run_id),
    )

    assert report.status == LLMJudgeStatus.SUCCEEDED
    assert report.overall_score == 84
    assert report.passed is True
    assert report.error_message is None
    assert report.safety is not None
    assert report.safety.score == 5

    assert len(client.calls) == 1
    assert client.calls[0]["model_name"] == "fake-judge-model"
    assert "generic-agent-case-001" in client.calls[0]["user_prompt"]
    assert "expected_behavior" in client.calls[0]["user_prompt"]
    assert "rule_evaluation" in client.calls[0]["user_prompt"]


@pytest.mark.asyncio
async def test_judge_service_accepts_json_inside_markdown_fence() -> None:
    evaluation_case = make_evaluation_case()
    case_run = make_case_run()
    client = FakeJudgeClient(
        response=f"```json\n{successful_judge_response()}\n```",
    )

    report = await LLMJudgeService(
        client=client,
        model_name="fake-judge-model",
    ).judge(
        evaluation_case=evaluation_case,
        case_run=case_run,
    )

    assert report.status == LLMJudgeStatus.SUCCEEDED
    assert report.overall_score == 84


@pytest.mark.asyncio
async def test_judge_service_records_invalid_json_as_judge_failure() -> None:
    evaluation_case = make_evaluation_case()
    case_run = make_case_run()
    client = FakeJudgeClient(response="This is not JSON.")

    report = await LLMJudgeService(
        client=client,
        model_name="fake-judge-model",
    ).judge(
        evaluation_case=evaluation_case,
        case_run=case_run,
    )

    assert report.status == LLMJudgeStatus.FAILED
    assert report.overall_score is None
    assert report.passed is None
    assert report.error_message is not None
    assert "JSON" in report.error_message


@pytest.mark.asyncio
async def test_judge_service_records_provider_exception_without_fake_score() -> None:
    evaluation_case = make_evaluation_case()
    case_run = make_case_run()
    client = FakeJudgeClient(
        error=LLMJudgeClientError(
            "Simulated Judge provider timeout.",
        ),
    )

    report = await LLMJudgeService(
        client=client,
        model_name="fake-judge-model",
    ).judge(
        evaluation_case=evaluation_case,
        case_run=case_run,
    )

    assert report.status == LLMJudgeStatus.FAILED
    assert report.overall_score is None
    assert report.passed is None
    assert report.error_message is not None
    assert "timeout" in report.error_message.lower()


@pytest.mark.asyncio
async def test_judge_service_skips_unsuccessful_target_agent_run() -> None:
    evaluation_case = make_evaluation_case()
    case_run = make_case_run(
        status=EvaluationExecutionStatus.FAILED,
        result_status="failed",
    )
    client = FakeJudgeClient(response=successful_judge_response())

    report = await LLMJudgeService(
        client=client,
        model_name="fake-judge-model",
    ).judge(
        evaluation_case=evaluation_case,
        case_run=case_run,
    )

    assert report.status == LLMJudgeStatus.SKIPPED
    assert report.overall_score is None
    assert report.passed is None
    assert report.error_message is not None
    assert client.calls == []


def test_fake_judge_client_matches_provider_protocol() -> None:
    client: LLMJudgeClient = FakeJudgeClient(
        response=successful_judge_response(),
    )

    assert client is not None
