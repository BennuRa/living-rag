"""Tests for true policy rule conflicts."""

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
    source_quote: str,
) -> PolicyRule:
    """Build one overlapping unrestricted refund rule."""

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


def test_overlapping_unrestricted_rules_are_conflict() -> None:
    """Two active rules with different values should conflict."""

    official_rule = make_rule(
        value=15,
        source_quote="正式政策：普通会员退款期限为 15 天。",
    )
    faq_rule = make_rule(
        value=30,
        source_quote="FAQ：所有会员可在 30 天内退款。",
    )

    comparison = compare_policy_rules(
        official_rule,
        faq_rule,
    )

    assert comparison.kind is PolicyRuleComparisonKind.CONFLICT
    assert comparison.severity is PolicyComparisonSeverity.HIGH
    assert comparison.left_rule_id == official_rule.id
    assert comparison.right_rule_id == faq_rule.id
    assert comparison.evidence == [
        official_rule.source_quote,
        faq_rule.source_quote,
    ]
    assert "冲突" in comparison.reason
    assert "审核" in comparison.recommended_action