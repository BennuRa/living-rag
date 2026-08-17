from __future__ import annotations

import asyncio
import os
from collections.abc import Iterable
from pathlib import Path

import httpx

from app.adapters.living_rag import LivingRAGAdapter
from app.schemas.evaluation_entities import (
    CaseRun,
    EvaluationCase,
    EvaluationDataset,
    EvaluationExecutionStatus,
    EvaluationRunArtifact,
)
from app.schemas.llm_judge import LLMJudgeReport, LLMJudgeStatus
from app.schemas.run_config import RunConfig
from app.schemas.trace_replay import TraceReplay
from app.services.batch_runner import BatchCaseRunner
from app.services.case_runner import CaseRunner
from app.services.evaluation_artifact_service import EvaluationArtifactService
from app.services.evaluation_run_service import EvaluationRunService
from app.services.llm_judge_artifact_service import (
    LLMJudgeArtifactService,
)
from app.services.llm_judge_service import LLMJudgeService
from app.services.openai_compatible_judge_client import (
    OpenAICompatibleJudgeClient,
)
from app.services.run_artifact_store import EvaluationRunArtifactStore
from app.services.task_dataset_loader import load_shared_agent_task_cases
from app.services.trace_replay_service import TraceReplayService
from app.settings import LLMJudgeSettings

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SHARED_TASK_DIR = PROJECT_ROOT.parent.parent / "shared" / "datasets" / "agent-tasks"
ARTIFACT_DIR = PROJECT_ROOT / "outputs" / "evaluation-runs"
LIVING_RAG_BASE_URL = os.getenv(
    "LIVING_RAG_BASE_URL",
    "http://127.0.0.1:8000",
)


def read_boolean_environment(
    variable_name: str,
    *,
    default: bool,
) -> bool:
    """Read one explicit boolean environment variable."""

    raw_value = os.getenv(variable_name)

    if raw_value is None:
        return default

    normalized_value = raw_value.strip().lower()

    if normalized_value in {"1", "true", "yes", "on"}:
        return True

    if normalized_value in {"0", "false", "no", "off"}:
        return False

    raise ValueError(
        f"{variable_name} must be one of true/false, 1/0, yes/no, or on/off.",
    )


# The Living RAG demo uses a local loopback address by default. httpx normally
# reads proxy environment variables, which can incorrectly route 127.0.0.1
# through a corporate or system proxy. Set LIVING_RAG_TRUST_ENV=true only when
# a deliberately configured proxy is required for a remote target endpoint.
LIVING_RAG_TRUST_ENV = read_boolean_environment(
    "LIVING_RAG_TRUST_ENV",
    default=False,
)


def build_evaluation_dataset(
    task_count: int,
) -> tuple[EvaluationDataset, list[EvaluationCase]]:
    tasks = load_shared_agent_task_cases()

    if len(tasks) < task_count:
        raise ValueError(
            f"Expected at least {task_count} task cases, but loaded only {len(tasks)}",
        )

    selected_tasks = tasks[:task_count]

    case_ids = [task.case_id for task in selected_tasks]
    unique_case_ids = set(case_ids)

    if len(unique_case_ids) != task_count:
        raise ValueError(
            "Selected task cases must have unique case_id values",
        )

    dataset = EvaluationDataset(
        name="living-rag-business-eligibility",
        source_path=str(SHARED_TASK_DIR),
        version="1",
    )

    evaluation_cases = [
        EvaluationCase(
            dataset_id=dataset.dataset_id,
            task=task,
        )
        for task in selected_tasks
    ]

    return dataset, evaluation_cases


def build_run_config(
    judge_settings: LLMJudgeSettings,
) -> RunConfig:
    """Build one persisted evaluation configuration from local settings."""

    return RunConfig(
        workflow_version="0.1.0",
        prompt_version="day22-llm-judge",
        timeout_seconds=30,
        max_concurrency=3,
        max_retries=1,
        cost_budget=1.0,
        llm_judge_enabled=judge_settings.enabled,
        llm_judge_model_name=(judge_settings.model_name if judge_settings.enabled else None),
        max_llm_judge_calls=(judge_settings.max_calls if judge_settings.enabled else 0),
    )


def case_run_trace_id(case_run: CaseRun) -> str | None:
    if case_run.trace_id:
        return case_run.trace_id

    if case_run.result is not None:
        return case_run.result.trace_id

    return None


async def load_trace_replays(
    client: httpx.AsyncClient,
    case_runs: Iterable[CaseRun],
) -> tuple[dict[str, TraceReplay], list[str]]:
    """Load available Living RAG traces without changing CaseRun outcomes."""

    trace_service = TraceReplayService()
    traces: dict[str, TraceReplay] = {}
    failures: list[str] = []

    seen_trace_ids: set[str] = set()

    for case_run in case_runs:
        trace_id = case_run_trace_id(case_run)

        if trace_id is None or trace_id in seen_trace_ids:
            continue

        seen_trace_ids.add(trace_id)

        try:
            response = await client.get(
                f"/runs/{trace_id}",
                headers={"Accept": "application/json"},
            )
            response.raise_for_status()

            raw_trace = response.json()
            traces[trace_id] = trace_service.build_replay(raw_trace)
        except (httpx.HTTPError, TypeError, ValueError) as exc:
            failures.append(f"{trace_id}: {exc}")

    return traces, failures


def attach_skipped_judge_reports(
    artifact: EvaluationRunArtifact,
    *,
    reason: str,
) -> EvaluationRunArtifact:
    """Record an explicit skipped Judge result for every CaseRun."""

    judge_reports = [
        LLMJudgeReport(
            case_run_id=case_run.case_run_id,
            status=LLMJudgeStatus.SKIPPED,
            error_message=reason,
        )
        for case_run in artifact.case_runs
    ]

    return artifact.model_copy(
        update={
            "llm_judge_evaluations": judge_reports,
        },
    )


async def evaluate_with_llm_judge(
    *,
    artifact: EvaluationRunArtifact,
    traces: dict[str, TraceReplay],
    judge_settings: LLMJudgeSettings,
) -> EvaluationRunArtifact:
    """Evaluate every CaseRun with Judge or record why Judge was skipped."""

    if not judge_settings.enabled:
        return attach_skipped_judge_reports(
            artifact,
            reason=("LLM Judge was skipped because LLM_JUDGE_ENABLED is false."),
        )

    if judge_settings.api_key is None:
        raise RuntimeError(
            "LLM Judge API key is missing after configuration validation.",
        )

    if judge_settings.model_name is None:
        raise RuntimeError(
            "LLM Judge model name is missing after configuration validation.",
        )

    async with httpx.AsyncClient(
        timeout=judge_settings.timeout_seconds,
    ) as judge_http_client:
        judge_client = OpenAICompatibleJudgeClient(
            http_client=judge_http_client,
            base_url=judge_settings.base_url,
            api_key=judge_settings.api_key.get_secret_value(),
            timeout_seconds=judge_settings.timeout_seconds,
        )
        judge_service = LLMJudgeService(
            client=judge_client,
            model_name=judge_settings.model_name,
        )
        judge_artifact_service = LLMJudgeArtifactService(
            llm_judge_service=judge_service,
            max_judge_calls=judge_settings.max_calls,
        )

        return await judge_artifact_service.evaluate_artifact(
            artifact=artifact,
            traces=traces,
        )


async def main() -> None:
    task_count = 20
    judge_settings = LLMJudgeSettings()

    dataset, evaluation_cases = build_evaluation_dataset(
        task_count=task_count,
    )
    config = build_run_config(judge_settings)

    async with httpx.AsyncClient(
        base_url=LIVING_RAG_BASE_URL,
        timeout=config.timeout_seconds,
        trust_env=LIVING_RAG_TRUST_ENV,
    ) as client:
        adapter = LivingRAGAdapter(client)
        case_runner = CaseRunner(adapter)
        batch_case_runner = BatchCaseRunner(case_runner)
        artifact_store = EvaluationRunArtifactStore(ARTIFACT_DIR)

        evaluation_run_service = EvaluationRunService(
            batch_case_runner=batch_case_runner,
            artifact_store=artifact_store,
        )

        evaluation_run, case_runs = await evaluation_run_service.execute(
            dataset=dataset,
            evaluation_cases=evaluation_cases,
            config=config,
        )

        artifact = artifact_store.load(
            evaluation_run.evaluation_run_id,
        )

        traces, trace_failures = await load_trace_replays(
            client=client,
            case_runs=case_runs,
        )

        rule_evaluated_artifact = EvaluationArtifactService().evaluate_artifact(
            artifact=artifact,
            traces=traces,
        )

    evaluated_artifact = await evaluate_with_llm_judge(
        artifact=rule_evaluated_artifact,
        traces=traces,
        judge_settings=judge_settings,
    )
    artifact_store.save(evaluated_artifact)

    artifact_path = ARTIFACT_DIR / f"{evaluation_run.evaluation_run_id}.json"

    succeeded_cases = [
        case_run for case_run in case_runs if case_run.status == EvaluationExecutionStatus.SUCCEEDED
    ]

    rule_reports = evaluated_artifact.rule_evaluations
    passed_rule_reports = [report for report in rule_reports if report.passed]
    blocked_rule_reports = [report for report in rule_reports if report.release_blocked]
    not_fully_evaluated_rule_reports = [
        report for report in rule_reports if report.not_evaluated_check_count > 0
    ]

    average_rule_score = (
        sum(report.score for report in rule_reports) / len(rule_reports) if rule_reports else 0.0
    )

    judge_reports = evaluated_artifact.llm_judge_evaluations
    succeeded_judge_reports = [
        report for report in judge_reports if report.status == LLMJudgeStatus.SUCCEEDED
    ]
    failed_judge_reports = [
        report for report in judge_reports if report.status == LLMJudgeStatus.FAILED
    ]
    skipped_judge_reports = [
        report for report in judge_reports if report.status == LLMJudgeStatus.SKIPPED
    ]

    average_judge_score = (
        sum(
            report.overall_score
            for report in succeeded_judge_reports
            if report.overall_score is not None
        )
        / len(succeeded_judge_reports)
        if succeeded_judge_reports
        else None
    )

    print(f"living_rag_base_url: {LIVING_RAG_BASE_URL}")
    print(f"living_rag_trust_env: {LIVING_RAG_TRUST_ENV}")
    print(f"dataset_id: {dataset.dataset_id}")
    print(f"evaluation_run_id: {evaluation_run.evaluation_run_id}")
    print(f"status: {evaluation_run.status}")
    print(f"total_cases: {evaluation_run.total_cases}")
    print(f"completed_cases: {evaluation_run.completed_cases}")
    print(f"succeeded_cases: {evaluation_run.succeeded_cases}")
    print(f"failed_cases: {evaluation_run.failed_cases}")
    print(f"timed_out_cases: {evaluation_run.timed_out_cases}")
    print(f"artifact_path: {artifact_path}")
    print()
    print("rule_evaluation_summary:")
    print(f"evaluated_case_count: {len(rule_reports)}")
    print(f"passed_case_count: {len(passed_rule_reports)}")
    print(f"blocked_case_count: {len(blocked_rule_reports)}")
    print(
        f"not_fully_evaluated_case_count: {len(not_fully_evaluated_rule_reports)}",
    )
    print(f"average_score: {average_rule_score:.2f}")
    print(f"trace_loaded_count: {len(traces)}")
    print(f"trace_load_failure_count: {len(trace_failures)}")
    print()
    print("llm_judge_summary:")
    print(f"enabled: {judge_settings.enabled}")
    print(f"configured_max_calls: {config.max_llm_judge_calls}")
    print(f"report_count: {len(judge_reports)}")
    print(f"succeeded_report_count: {len(succeeded_judge_reports)}")
    print(f"failed_report_count: {len(failed_judge_reports)}")
    print(f"skipped_report_count: {len(skipped_judge_reports)}")

    if average_judge_score is not None:
        print(f"average_score: {average_judge_score:.2f}")

    if trace_failures:
        print()
        print("trace_load_failures:")

        for failure in trace_failures:
            print(f"- {failure}")

    print()
    print("case_results:")

    case_by_id = {
        evaluation_case.evaluation_case_id: evaluation_case for evaluation_case in evaluation_cases
    }
    rule_report_by_case_run_id = {report.case_run_id: report for report in rule_reports}
    judge_report_by_case_run_id = {report.case_run_id: report for report in judge_reports}

    for case_run in case_runs:
        evaluation_case = case_by_id[case_run.evaluation_case_id]
        result = case_run.result
        rule_report = rule_report_by_case_run_id.get(case_run.case_run_id)
        judge_report = judge_report_by_case_run_id.get(case_run.case_run_id)

        print(
            f"- case_id={evaluation_case.task.case_id} "
            f"status={case_run.status} "
            f"attempt_count={case_run.attempt_count} "
            f"trace_id={case_run.trace_id} "
            f"latency_ms={case_run.latency_ms} "
            f"error={case_run.error_message}",
        )

        if result is not None and result.final_answer:
            print(f"  final_answer={result.final_answer}")

        if rule_report is not None:
            print(
                f"  rule_score={rule_report.score:.2f} "
                f"rule_passed={rule_report.passed} "
                f"release_blocked={rule_report.release_blocked} "
                f"not_evaluated={rule_report.not_evaluated_check_count}",
            )

        if judge_report is not None:
            print(
                f"  judge_status={judge_report.status} "
                f"judge_score={judge_report.overall_score} "
                f"judge_passed={judge_report.passed} "
                f"judge_error={judge_report.error_message}",
            )

    if not artifact_path.is_file():
        raise RuntimeError(
            f"Expected evaluation artifact was not created: {artifact_path}",
        )

    successful_trace_count = sum(1 for case_run in succeeded_cases if case_run_trace_id(case_run))

    print()
    print(f"successful_cases_with_trace_id: {successful_trace_count}")

    if successful_trace_count == 0:
        raise RuntimeError(
            "No successful case returned a trace_id. "
            "Check the Living RAG API and trace integration.",
        )


if __name__ == "__main__":
    asyncio.run(main())
