import pytest
from pydantic import ValidationError

from app.schemas.agent_task_case import (
    AgentTaskCase,
    AgentTaskCategory,
    ExpectedCitation,
)
from app.schemas.fault_injection import (
    FaultInjectionConfig,
    FaultInjectionType,
)


def test_create_complete_agent_task_case() -> None:
    """A complete Day 16 task keeps all structured evaluation fields."""

    task_case = AgentTaskCase(
        case_id="qa-policy-current-001",
        category=AgentTaskCategory.NORMAL_POLICY_QA,
        name="查询当前退款时限",
        user_input="普通会员签收后多久可以申请退款？",
        context={
            "user_external_id": "USR001",
            "order_no": None,
        },
        expected_route="policy_qa",
        expected_citations=[
            ExpectedCitation(
                policy_key="REFUND-POLICY",
                version=3,
                source_type="official_policy",
                chunk_contains="15天",
            )
        ],
        expected_behavior=[
            "回答当前有效退款期限",
            "引用退款政策 v3",
        ],
        forbidden_behavior=[
            "引用退款政策 v1 作为当前规则",
            "没有证据时编造退款期限",
        ],
        failure_conditions=[
            "没有返回任何引用",
            "引用了已经废弃的文档版本",
        ],
        tags=[
            "refund",
            "policy",
            "citation",
        ],
        metadata={
            "difficulty": "easy",
            "source": "day-16",
        },
    )

    assert task_case.case_id == "qa-policy-current-001"
    assert task_case.category is AgentTaskCategory.NORMAL_POLICY_QA
    assert task_case.name == "查询当前退款时限"
    assert task_case.user_input == "普通会员签收后多久可以申请退款？"
    assert task_case.context["user_external_id"] == "USR001"
    assert task_case.expected_route == "policy_qa"
    assert len(task_case.expected_citations) == 1
    assert task_case.expected_citations[0].policy_key == "REFUND-POLICY"
    assert task_case.expected_citations[0].version == 3
    assert task_case.expected_citations[0].source_type == "official_policy"
    assert task_case.expected_citations[0].chunk_contains == "15天"
    assert len(task_case.expected_behavior) == 2
    assert len(task_case.forbidden_behavior) == 2
    assert len(task_case.failure_conditions) == 2


def test_generate_case_id_when_case_id_is_omitted() -> None:
    """A task receives a generated string identifier when no ID is provided."""

    task_case = AgentTaskCase(
        name="默认任务编号测试",
        user_input="当前退款政策是什么？",
        expected_behavior="回答时必须提供政策引用。",
    )

    assert task_case.case_id.startswith("generated-")
    assert len(task_case.case_id) > len("generated-")
    assert task_case.category is AgentTaskCategory.NORMAL_POLICY_QA
    assert task_case.expected_route == "policy_qa"


def test_normalize_legacy_behavior_string_to_list() -> None:
    """Legacy string behavior values are normalized to one-item lists."""

    task_case = AgentTaskCase(
        name="兼容旧版行为字段",
        user_input="当前退款政策是什么？",
        expected_behavior="必须引用当前有效政策。",
        forbidden_behavior="不能引用过期政策。",
        failure_conditions="没有引用时判定失败。",
    )

    assert task_case.expected_behavior == ["必须引用当前有效政策。"]
    assert task_case.forbidden_behavior == ["不能引用过期政策。"]
    assert task_case.failure_conditions == ["没有引用时判定失败。"]


def test_empty_expected_citations_and_fault_injection_are_valid() -> None:
    """A task can have no expected citation and no injected fault."""

    task_case = AgentTaskCase(
        name="无引用任务",
        category=AgentTaskCategory.ADVERSARIAL,
        user_input="请回答一个知识库中不存在的问题。",
        expected_route="safe_unknown_response",
        expected_citations=[],
        expected_behavior=[
            "说明当前知识库没有足够证据",
            "不要编造事实",
        ],
        fault_injection=None,
    )

    assert task_case.expected_citations == []
    assert task_case.fault_injection is None
    assert task_case.expected_route == "safe_unknown_response"


def test_fault_injection_can_be_embedded_in_task_case() -> None:
    """A fault injection task keeps its deterministic fault configuration."""

    task_case = AgentTaskCase(
        case_id="fault-tool-timeout-001",
        category=AgentTaskCategory.FAULT_INJECTION,
        name="订单工具超时后安全降级",
        user_input="订单 O2025001 可以退款吗？",
        context={
            "order_no": "O2025001",
        },
        expected_route="refund_eligibility",
        expected_behavior=[
            "说明订单工具暂时不可用",
            "不要猜测退款资格",
        ],
        forbidden_behavior=[
            "在没有订单数据时直接判断可以退款",
        ],
        failure_conditions=[
            "工具失败后仍然给出确定性退款结论",
        ],
        fault_injection=FaultInjectionConfig(
            enabled=True,
            fault_type=FaultInjectionType.TOOL_TIMEOUT,
            target_tool="get_order",
            message="模拟订单查询超时",
            parameters={
                "timeout_ms": 100,
            },
        ),
    )

    assert task_case.fault_injection is not None
    assert task_case.fault_injection.enabled is True
    assert (
        task_case.fault_injection.fault_type
        is FaultInjectionType.TOOL_TIMEOUT
    )
    assert task_case.fault_injection.target_tool == "get_order"
    assert task_case.fault_injection.parameters["timeout_ms"] == 100


def test_expected_citation_version_must_be_positive() -> None:
    """An expected citation cannot point to version zero or a negative version."""

    with pytest.raises(ValidationError):
        ExpectedCitation(
            policy_key="REFUND-POLICY",
            version=0,
        )

    with pytest.raises(ValidationError):
        ExpectedCitation(
            policy_key="REFUND-POLICY",
            version=-1,
        )


def test_reject_empty_required_text_fields() -> None:
    """Required task text fields cannot be empty."""

    with pytest.raises(ValidationError):
        AgentTaskCase(
            name="",
            user_input="当前退款政策是什么？",
            expected_behavior=["必须提供引用。"],
        )

    with pytest.raises(ValidationError):
        AgentTaskCase(
            name="空用户输入",
            user_input="",
            expected_behavior=["必须提供引用。"],
        )

    with pytest.raises(ValidationError):
        AgentTaskCase(
            name="空预期路由",
            user_input="当前退款政策是什么？",
            expected_route="",
            expected_behavior=["必须提供引用。"],
        )


def test_reject_unknown_task_fields() -> None:
    """The task schema rejects undeclared fields."""

    with pytest.raises(ValidationError):
        AgentTaskCase(
            name="未知字段测试",
            user_input="当前退款政策是什么？",
            expected_behavior=["必须提供引用。"],
            unsupported_field="should be rejected",
        )


def test_reject_unknown_citation_fields() -> None:
    """The expected citation schema rejects undeclared fields."""

    with pytest.raises(ValidationError):
        ExpectedCitation(
            policy_key="REFUND-POLICY",
            version=3,
            unsupported_field="should be rejected",
        )


def test_reject_invalid_task_category() -> None:
    """A task category must be one of the declared categories."""

    with pytest.raises(ValidationError):
        AgentTaskCase(
            name="非法类别测试",
            category="unknown_category",
            user_input="当前退款政策是什么？",
            expected_behavior=["必须提供引用。"],
        )
