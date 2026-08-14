import pytest
from pydantic import ValidationError

from app.schemas.agent_task_case import AgentTaskCase, AgentTaskCategory
from app.schemas.fault_injection import FaultInjectionConfig, FaultInjectionType


def test_task_case_normalizes_legacy_string_lists() -> None:
    task = AgentTaskCase(
        case_id="eligibility-001",
        name="普通会员订单退款资格",
        category="order_membership_eligibility",
        user_input="订单 O2025001 签收 12 天了，能退款吗？",
        context={
            "order_no": "O2025001",
            "user_external_id": "USR001",
        },
        expected_route="refund_eligibility",
        expected_citations=[
            {
                "policy_key": "REFUND-POLICY",
                "version": 3,
                "source_type": "official_policy",
            }
        ],
        expected_behavior="调用订单和会员查询",
        forbidden_behavior="让 LLM 脱离订单数据直接裁定",
        failure_conditions="没有查询订单",
        fault_injection={
            "enabled": True,
            "fault_type": "tool_timeout",
            "target_tool": "get_order",
        },
    )

    assert task.category is AgentTaskCategory.ORDER_MEMBERSHIP_ELIGIBILITY
    assert task.expected_behavior == ["调用订单和会员查询"]
    assert task.forbidden_behavior == ["让 LLM 脱离订单数据直接裁定"]
    assert task.failure_conditions == ["没有查询订单"]
    assert task.expected_citations[0].version == 3
    assert task.fault_injection is not None
    assert task.fault_injection.fault_type is FaultInjectionType.TOOL_TIMEOUT


def test_fault_config_creates_independent_parameter_dictionaries() -> None:
    first_config = FaultInjectionConfig()
    second_config = FaultInjectionConfig()

    first_config.parameters["delay_seconds"] = 30

    assert first_config.parameters == {"delay_seconds": 30}
    assert second_config.parameters == {}


@pytest.mark.parametrize(
    ("kwargs", "field_path"),
    [
        ({"expected_behavior": []}, ("expected_behavior",)),
        (
            {"expected_citations": [{"policy_key": "REFUND-POLICY", "version": 0}]},
            ("expected_citations", 0, "version"),
        ),
        ({"category": "unsupported_category"}, ("category",)),
        ({"unknown_field": "unexpected"}, ("unknown_field",)),
    ],
)
def test_task_case_rejects_invalid_data(
    kwargs: dict[str, object],
    field_path: tuple[object, ...],
) -> None:
    valid_case = {
        "case_id": "valid-case",
        "name": "有效任务",
        "user_input": "当前退款政策是什么？",
        "expected_behavior": ["检索当前有效政策"],
    }

    with pytest.raises(ValidationError) as exc_info:
        AgentTaskCase(**{**valid_case, **kwargs})

    assert exc_info.value.errors()[0]["loc"] == field_path