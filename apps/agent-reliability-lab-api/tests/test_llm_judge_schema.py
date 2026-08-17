from __future__ import annotations

from uuid import uuid4

import pytest

from app.schemas.llm_judge import (
    LLMJudgeDimensionScore,
    LLMJudgeReport,
    LLMJudgeStatus,
)


def make_dimension(
    score: int = 4,
    reason: str = "The response satisfies this quality dimension.",
) -> LLMJudgeDimensionScore:
    return LLMJudgeDimensionScore(
        score=score,
        reason=reason,
    )


def make_succeeded_report() -> LLMJudgeReport:
    return LLMJudgeReport(
        case_run_id=uuid4(),
        judge_model="test-judge-model",
        status=LLMJudgeStatus.SUCCEEDED,
        overall_score=82,
        passed=True,
        conclusion_correctness=make_dimension(),
        answer_completeness=make_dimension(),
        citation_support=make_dimension(),
        conflict_handling=make_dimension(),
        safety=make_dimension(score=5),
        evidence_basedness=make_dimension(score=3),
        reasoning="The answer is broadly correct but needs stronger evidence.",
    )


def test_succeeded_llm_judge_report_requires_score_passed_and_reasoning() -> None:
    report = make_succeeded_report()

    assert report.status == LLMJudgeStatus.SUCCEEDED
    assert report.overall_score == 82
    assert report.passed is True
    assert report.reasoning is not None
    assert report.error_message is None


@pytest.mark.parametrize(
    ("field_name", "field_value", "error_message"),
    [
        (
            "overall_score",
            None,
            "Succeeded LLM Judge report requires overall_score",
        ),
        (
            "passed",
            None,
            "Succeeded LLM Judge report requires passed",
        ),
        (
            "reasoning",
            None,
            "Succeeded LLM Judge report requires reasoning",
        ),
    ],
)
def test_succeeded_llm_judge_report_rejects_missing_required_fields(
    field_name: str,
    field_value: object,
    error_message: str,
) -> None:
    payload = make_succeeded_report().model_dump()
    payload[field_name] = field_value

    with pytest.raises(ValueError, match=error_message):
        LLMJudgeReport.model_validate(payload)


def test_failed_llm_judge_report_records_error_without_fake_score() -> None:
    report = LLMJudgeReport(
        case_run_id=uuid4(),
        judge_model="test-judge-model",
        status=LLMJudgeStatus.FAILED,
        error_message="Judge API timed out after 10 seconds.",
    )

    assert report.status == LLMJudgeStatus.FAILED
    assert report.error_message == "Judge API timed out after 10 seconds."
    assert report.overall_score is None
    assert report.passed is None


def test_failed_llm_judge_report_rejects_fake_score() -> None:
    with pytest.raises(
        ValueError,
        match="Failed LLM Judge report cannot include overall_score",
    ):
        LLMJudgeReport(
            case_run_id=uuid4(),
            status=LLMJudgeStatus.FAILED,
            overall_score=0,
            error_message="Judge API timed out after 10 seconds.",
        )


def test_failed_llm_judge_report_requires_error_message() -> None:
    with pytest.raises(
        ValueError,
        match="Failed LLM Judge report requires error_message",
    ):
        LLMJudgeReport(
            case_run_id=uuid4(),
            status=LLMJudgeStatus.FAILED,
        )


def test_skipped_llm_judge_report_has_no_score_or_pass_decision() -> None:
    report = LLMJudgeReport(
        case_run_id=uuid4(),
        status=LLMJudgeStatus.SKIPPED,
        error_message="Judge call limit reached for this evaluation run.",
    )

    assert report.status == LLMJudgeStatus.SKIPPED
    assert report.overall_score is None
    assert report.passed is None
    assert report.error_message is not None


def test_dimension_score_rejects_out_of_range_value() -> None:
    with pytest.raises(ValueError):
        LLMJudgeDimensionScore(
            score=6,
            reason="Scores must stay within the 0 to 5 range.",
        )