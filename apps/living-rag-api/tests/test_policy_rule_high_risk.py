"""Tests for high-risk policy rule detection."""

from datetime import UTC, datetime
from uuid import uuid4

from app.models.policy_rule import PolicyRule
from app.schemas.policy_comparison import (
    PolicyComparisonSeverity,
    PolicyRuleComparisonKind,
)
from app.services.policy_rule_comparison import (
    _is_high_risk_rule,
    compare_policy_rules,
)


TEST_EFFECTIVE_AT = datetime(
    2025,
    7,
    1,
    tzinfo=UTC,
)


def make_rule(
    *,
    value: object,
    source_quote: str,
) -> PolicyRule:
    """Build one in-memory rule for high-risk tests."""

    return PolicyRule(
        id=uuid4(),
        document_version_id=uuid4(),
        rule_key="refund.window_days",
        value=value,
        conditions={},
        source_quote=source_quote,
        effective_at=TEST_EFFECTIVE_AT,
        expires_at=None,
        confidence=0.95,
    )


def test_chinese_unlimited_refund_text_is_high_risk() -> None:
    """Chinese unlimited-refund wording should be detected."""

    rule = make_rule(
        value="all",
        source_quote="所有商品永久支持退款，无时间限制。",
    )

    assert _is_high_risk_rule(rule)


def test_english_unlimited_value_is_case_insensitive() -> None:
    """English high-risk values should be detected regardless of case."""

    rule = make_rule(
        value="Unlimited",
        source_quote="Operation notice.",
    )

    assert _is_high_risk_rule(rule)


def test_normal_refund_rule_is_not_high_risk() -> None:
    """A normal fifteen-day policy should not be marked high-risk."""

    rule = make_rule(
        value=15,
        source_quote="普通会员签收后 15 天内可以申请退款。",
    )

    assert not _is_high_risk_rule(rule)


def test_high_risk_rule_takes_priority_over_conflict() -> None:
    """A high-risk rule should not be reduced to an ordinary conflict."""

    official_rule = make_rule(
        value=15,
        source_quote="正式政策：退款期限为 15 天。",
    )
    risky_rule = make_rule(
        value="unlimited",
        source_quote="运营通知：所有商品永久支持退款。",
    )

    comparison = compare_policy_rules(
        official_rule,
        risky_rule,
    )

    assert comparison.kind is PolicyRuleComparisonKind.HIGH_RISK_ERROR
    assert comparison.severity is PolicyComparisonSeverity.HIGH
    assert comparison.evidence == [
        official_rule.source_quote,
        risky_rule.source_quote,
    ]
    assert comparison.reason
    assert comparison.recommended_action