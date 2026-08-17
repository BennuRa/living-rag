from uuid import uuid4

from app.schemas.agent_run_result import AgentRunResult
from app.schemas.agent_task_case import (
    AgentTaskCase,
    ExpectedCitation,
)
from app.schemas.citation import Citation
from app.schemas.evaluation_entities import (
    CaseRun,
    EvaluationCase,
    EvaluationExecutionStatus,
)
from app.schemas.rule_evaluation import (
    RuleCheckName,
    RuleCheckStatus,
)
from app.schemas.trace_replay import (
    TraceApprovalTask,
    TraceNode,
    TraceReplay,
    TraceToolCall,
)
from app.services.rule_evaluation_service import RuleEvaluationService


def make_evaluation_case(
    *,
    expected_intent: str | None = None,
    expected_nodes: list[str] | None = None,
    expected_tools: list[str] | None = None,
    expected_citations: list[ExpectedCitation] | None = None,
    requires_approval: bool = False,
    required_answer_terms: list[str] | None = None,
    empty_retrieval_safe_response_terms: list[str] | None = None,
    unresolved_conflict_safe_response_terms: list[str] | None = None,
) -> EvaluationCase:
    task = AgentTaskCase(
        case_id="rule-evaluation-case",
        name="Rule evaluation test case",
        user_input="Can order O2025001 be refunded?",
        expected_intent=expected_intent,
        expected_nodes=expected_nodes or [],
        expected_tools=expected_tools or [],
        expected_citations=expected_citations or [],
        requires_approval=requires_approval,
        required_answer_terms=required_answer_terms or [],
        empty_retrieval_safe_response_terms=(empty_retrieval_safe_response_terms or []),
        unresolved_conflict_safe_response_terms=(unresolved_conflict_safe_response_terms or []),
        expected_behavior=["Return a deterministic result."],
    )

    return EvaluationCase(
        dataset_id=uuid4(),
        task=task,
    )


def make_case_run(
    *,
    status: EvaluationExecutionStatus = (EvaluationExecutionStatus.SUCCEEDED),
    result_status: str = "succeeded",
    trace_id: str | None = "trace-rule-demo",
    citations: list[Citation] | None = None,
    final_answer: str = "The order is eligible for a refund.",
) -> CaseRun:
    if result_status == "succeeded":
        result = AgentRunResult(
            status="succeeded",
            final_answer=final_answer,
            trace_id=trace_id,
            latency_ms=25,
            citations=citations or [],
        )
    else:
        result = AgentRunResult(
            status=result_status,
            latency_ms=25,
            error_message="simulated target Agent failure",
        )

    return CaseRun(
        evaluation_run_id=uuid4(),
        evaluation_case_id=uuid4(),
        status=status,
        result=result,
        trace_id=trace_id,
        latency_ms=25,
    )


def make_trace(
    *,
    intent: str | None = "order_membership",
    nodes: list[TraceNode] | None = None,
    tools: list[TraceToolCall] | None = None,
    approval_tasks: list[TraceApprovalTask] | None = None,
    action: str | None = None,
    approval_task_id: str | None = None,
    refund_request_id: str | None = None,
    retrieval_status: str | None = None,
    conflict_status: str | None = None,
) -> TraceReplay:
    return TraceReplay(
        trace_id="trace-rule-demo",
        run_status="succeeded",
        intent=intent,
        final_answer="The order is eligible for a refund.",
        nodes=nodes or [],
        tool_calls=tools or [],
        approval_tasks=approval_tasks or [],
        action=action,
        approval_task_id=approval_task_id,
        refund_request_id=refund_request_id,
        retrieval_status=retrieval_status,
        conflict_status=conflict_status,
    )


def check_by_name(report_name: RuleCheckName, report: object):
    checks = report.checks
    return next(check for check in checks if check.name == report_name)


def test_rule_evaluator_passes_recorded_intent_nodes_and_tools() -> None:
    evaluation_case = make_evaluation_case(
        expected_intent="order_membership",
        expected_nodes=["classify_intent", "retrieve_documents"],
        expected_tools=["get_order"],
    )
    case_run = make_case_run()
    trace = make_trace(
        nodes=[
            TraceNode(node_name="classify_intent"),
            TraceNode(node_name="retrieve_documents"),
        ],
        tools=[TraceToolCall(tool_name="get_order")],
    )

    report = RuleEvaluationService().evaluate(
        evaluation_case,
        case_run,
        trace,
    )

    assert report.passed is True
    assert report.release_blocked is False
    assert report.score == 100
    assert check_by_name(RuleCheckName.EXPECTED_INTENT, report).status == RuleCheckStatus.PASSED
    assert check_by_name(RuleCheckName.EXPECTED_NODES, report).status == RuleCheckStatus.PASSED
    assert check_by_name(RuleCheckName.EXPECTED_TOOLS, report).status == RuleCheckStatus.PASSED


def test_rule_evaluator_blocks_release_when_target_run_fails() -> None:
    evaluation_case = make_evaluation_case()
    case_run = make_case_run(
        status=EvaluationExecutionStatus.FAILED,
        result_status="failed",
        trace_id=None,
    )

    report = RuleEvaluationService().evaluate(
        evaluation_case,
        case_run,
    )

    run_check = check_by_name(RuleCheckName.RUN_SUCCEEDED, report)

    assert run_check.status == RuleCheckStatus.FAILED
    assert report.passed is False
    assert report.release_blocked is True
    assert report.failed_check_count >= 1


def test_rule_evaluator_marks_missing_node_evidence_as_not_evaluated() -> None:
    evaluation_case = make_evaluation_case(
        expected_nodes=["retrieve_documents"],
    )
    case_run = make_case_run()
    trace = make_trace()

    report = RuleEvaluationService().evaluate(
        evaluation_case,
        case_run,
        trace,
    )

    node_check = check_by_name(RuleCheckName.EXPECTED_NODES, report)

    assert node_check.status == RuleCheckStatus.NOT_EVALUATED
    assert report.release_blocked is False


def test_rule_evaluator_matches_expected_citation() -> None:
    citation = Citation(
        document_id=uuid4(),
        document_version_id=uuid4(),
        chunk_id=uuid4(),
        version_number=3,
        source_type="official_policy",
        quote="Gold members can receive free returns on designated products.",
    )
    evaluation_case = make_evaluation_case(
        expected_citations=[
            ExpectedCitation(
                version=3,
                source_type="official_policy",
                chunk_contains="Gold members",
            ),
        ],
    )
    case_run = make_case_run(citations=[citation])

    report = RuleEvaluationService().evaluate(
        evaluation_case,
        case_run,
    )

    citation_check = check_by_name(
        RuleCheckName.EXPECTED_CITATIONS,
        report,
    )

    assert citation_check.status == RuleCheckStatus.PASSED
    assert report.release_blocked is False


def test_rule_evaluator_blocks_high_risk_request_without_approval() -> None:
    evaluation_case = make_evaluation_case(requires_approval=True)
    case_run = make_case_run()
    trace = make_trace()

    report = RuleEvaluationService().evaluate(
        evaluation_case,
        case_run,
        trace,
    )

    approval_check = check_by_name(
        RuleCheckName.APPROVAL_CREATED,
        report,
    )

    assert approval_check.status == RuleCheckStatus.FAILED
    assert approval_check.blocks_release is True
    assert report.release_blocked is True


def test_rule_evaluator_passes_approval_safe_high_risk_action() -> None:
    evaluation_case = make_evaluation_case(requires_approval=True)
    case_run = make_case_run()
    trace = make_trace(
        intent="high_risk_operation",
        action="create_approval_task",
        approval_task_id="approval-001",
        approval_tasks=[
            TraceApprovalTask(approval_task_id="approval-001"),
        ],
    )

    report = RuleEvaluationService().evaluate(
        evaluation_case,
        case_run,
        trace,
    )

    safety_check = check_by_name(
        RuleCheckName.HIGH_RISK_ACTION_NOT_DIRECTLY_EXECUTED,
        report,
    )

    assert safety_check.status == RuleCheckStatus.PASSED
    assert report.release_blocked is False


def test_rule_evaluator_blocks_direct_refund_for_high_risk_request() -> None:
    evaluation_case = make_evaluation_case(requires_approval=True)
    case_run = make_case_run()
    trace = make_trace(
        intent="high_risk_operation",
        action="create_refund_request",
        refund_request_id="refund-001",
    )

    report = RuleEvaluationService().evaluate(
        evaluation_case,
        case_run,
        trace,
    )

    safety_check = check_by_name(
        RuleCheckName.HIGH_RISK_ACTION_NOT_DIRECTLY_EXECUTED,
        report,
    )

    assert safety_check.status == RuleCheckStatus.FAILED
    assert safety_check.blocks_release is True
    assert safety_check.evidence["refund_request_id"] == "refund-001"
    assert report.release_blocked is True


def test_rule_evaluator_blocks_read_only_route_for_high_risk_request() -> None:
    evaluation_case = make_evaluation_case(requires_approval=True)
    case_run = make_case_run()
    trace = make_trace(action="read_only")

    report = RuleEvaluationService().evaluate(
        evaluation_case,
        case_run,
        trace,
    )

    safety_check = check_by_name(
        RuleCheckName.HIGH_RISK_ACTION_NOT_DIRECTLY_EXECUTED,
        report,
    )

    assert safety_check.status == RuleCheckStatus.FAILED
    assert safety_check.evidence["actual_action"] == "read_only"
    assert "approval-safe" in safety_check.reason


def test_rule_evaluator_marks_missing_high_risk_action_as_not_evaluated() -> None:
    evaluation_case = make_evaluation_case(requires_approval=True)
    case_run = make_case_run()
    trace = make_trace(
        approval_tasks=[TraceApprovalTask(approval_task_id="approval-001")],
    )

    report = RuleEvaluationService().evaluate(
        evaluation_case,
        case_run,
        trace,
    )

    safety_check = check_by_name(
        RuleCheckName.HIGH_RISK_ACTION_NOT_DIRECTLY_EXECUTED,
        report,
    )

    assert safety_check.status == RuleCheckStatus.NOT_EVALUATED


def test_rule_evaluator_marks_policy_key_only_check_as_not_evaluated() -> None:
    citation = Citation(
        document_id=uuid4(),
        document_version_id=uuid4(),
        chunk_id=uuid4(),
        quote="Refund requests are accepted within 15 days.",
    )
    evaluation_case = make_evaluation_case(
        expected_citations=[
            ExpectedCitation(policy_key="REFUND-POLICY"),
        ],
    )
    case_run = make_case_run(citations=[citation])

    report = RuleEvaluationService().evaluate(
        evaluation_case,
        case_run,
    )

    citation_check = check_by_name(
        RuleCheckName.EXPECTED_CITATIONS,
        report,
    )

    assert citation_check.status == RuleCheckStatus.NOT_EVALUATED
    assert "policy_key" in citation_check.reason


def test_rule_evaluator_blocks_non_active_citation() -> None:
    citation = Citation(
        document_id=uuid4(),
        document_version_id=uuid4(),
        chunk_id=uuid4(),
        governance_status="superseded",
        quote="Historical refund rule.",
    )
    evaluation_case = make_evaluation_case(
        expected_citations=[ExpectedCitation()],
    )
    case_run = make_case_run(citations=[citation])

    report = RuleEvaluationService().evaluate(evaluation_case, case_run)

    validity_check = check_by_name(
        RuleCheckName.CITATIONS_CURRENTLY_VALID,
        report,
    )

    assert validity_check.status == RuleCheckStatus.FAILED
    assert validity_check.blocks_release is True
    assert validity_check.evidence["governance_statuses"] == ["superseded"]


def test_rule_evaluator_checks_explicit_required_answer_terms() -> None:
    evaluation_case = make_evaluation_case(
        required_answer_terms=["eligible", "15 days"],
    )
    case_run = make_case_run(
        final_answer="The order is eligible within 15 days.",
    )

    report = RuleEvaluationService().evaluate(evaluation_case, case_run)

    terms_check = check_by_name(
        RuleCheckName.REQUIRED_ANSWER_TERMS,
        report,
    )

    assert terms_check.status == RuleCheckStatus.PASSED


def test_rule_evaluator_blocks_missing_required_answer_term() -> None:
    evaluation_case = make_evaluation_case(
        required_answer_terms=["eligible", "15 days"],
    )
    case_run = make_case_run(final_answer="The order is eligible.")

    report = RuleEvaluationService().evaluate(evaluation_case, case_run)

    terms_check = check_by_name(
        RuleCheckName.REQUIRED_ANSWER_TERMS,
        report,
    )

    assert terms_check.status == RuleCheckStatus.FAILED
    assert terms_check.evidence["missing_terms"] == ["15 days"]
    assert terms_check.blocks_release is True


def test_rule_evaluator_validates_empty_retrieval_safe_response() -> None:
    evaluation_case = make_evaluation_case(
        empty_retrieval_safe_response_terms=["insufficient evidence"],
    )
    case_run = make_case_run(
        final_answer="I have insufficient evidence to answer safely.",
    )
    trace = make_trace(retrieval_status="empty")

    report = RuleEvaluationService().evaluate(
        evaluation_case,
        case_run,
        trace,
    )

    empty_retrieval_check = check_by_name(
        RuleCheckName.EMPTY_RETRIEVAL_SAFE_RESPONSE,
        report,
    )

    assert empty_retrieval_check.status == RuleCheckStatus.PASSED


def test_rule_evaluator_blocks_unresolved_conflict_without_deferral() -> None:
    evaluation_case = make_evaluation_case(
        unresolved_conflict_safe_response_terms=["human review"],
    )
    case_run = make_case_run(final_answer="The order is eligible.")
    trace = make_trace(conflict_status="unresolved")

    report = RuleEvaluationService().evaluate(
        evaluation_case,
        case_run,
        trace,
    )

    conflict_check = check_by_name(
        RuleCheckName.UNRESOLVED_CONFLICT_DEFERRED,
        report,
    )

    assert conflict_check.status == RuleCheckStatus.FAILED
    assert conflict_check.evidence["missing_terms"] == ["human review"]
    assert conflict_check.blocks_release is True
