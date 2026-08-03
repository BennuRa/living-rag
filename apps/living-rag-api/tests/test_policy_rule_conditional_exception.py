"""Tests for conditional policy rule exceptions."""

from datetime import UTC, datetime
from uuid import uuid4

from app.models.policy_rule import PolicyRule
from app.schemas.policy_comparison import (
    PolicyComparisonSeverity,
    PolicyRuleComparisonKind,
)
from app.services.policy_rule_comparison import compare_policy_rules


TEST_EFFECTIVE_AT = datetime(
    2025,
    7,
    1,
    tzinfo=UTC,
)


def make_rule(
    *,
    value: object,
    conditions: dict[str, object],
    source_quote: str,
) -> PolicyRule:
    """Build one in-memory rule for conditional exception tests."""

    return PolicyRule(
        id=uuid4(),
        document_version_id=uuid4(),
        rule_key="refund.window_days",
        value=value,
        conditions=conditions,
        source_quote=source_quote,
        effective_at=TEST_EFFECTIVE_AT,
        expires_at=None,
        confidence=0.95,
    )


def test_narrow_campaign_rule_is_conditional_exception() -> None:
    """A campaign-specific rule should be a conditional exception."""

    official_rule = make_rule(
        value=15,
        conditions={},
        source_quote="正式政策：普通退款期限为 15 天。",
    )
    campaign_rule = make_rule(
        value=30,
        conditions={
            "campaign": "double_11",
        },
        source_quote="双十一公告：活动订单可在 30 天内退款。",
    )

    comparison = compare_policy_rules(
        official_rule,
        campaign_rule,
    )

    assert (
        comparison.kind
        is PolicyRuleComparisonKind.CONDITIONAL_EXCEPTION
    )
    assert comparison.severity is PolicyComparisonSeverity.MEDIUM
    assert comparison.rule_key.value == "refund.window_days"

    assert comparison.left_rule_id == official_rule.id
    assert comparison.right_rule_id == campaign_rule.id
    assert (
        comparison.left_document_version_id
        == official_rule.document_version_id
    )
    assert (
        comparison.right_document_version_id
        == campaign_rule.document_version_id
    )

    assert comparison.reason
    assert comparison.recommended_action
    assert comparison.evidence == [
        official_rule.source_quote,
        campaign_rule.source_quote,
    ]


def test_conditional_exception_is_detected_when_rules_are_reversed(
) -> None:
    """Specificity detection should work in either argument order."""

    campaign_rule = make_rule(
        value=30,
        conditions={
            "campaign": "double_11",
        },
        source_quote="双十一公告：活动订单可在 30 天内退款。",
    )
    official_rule = make_rule(
        value=15,
        conditions={},
        source_quote="正式政策：普通退款期限为 15 天。",
    )

    comparison = compare_policy_rules(
        campaign_rule,
        official_rule,
    )

    assert (
        comparison.kind
        is PolicyRuleComparisonKind.CONDITIONAL_EXCEPTION
    )
    assert comparison.severity is PolicyComparisonSeverity.MEDIUM
    assert comparison.evidence == [
        campaign_rule.source_quote,
        official_rule.source_quote,
    ]