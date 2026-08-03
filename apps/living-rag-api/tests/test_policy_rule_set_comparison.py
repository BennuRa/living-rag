"""Tests for policy rule set comparison."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.models.policy_rule import PolicyRule
from app.schemas.policy_comparison import (
    PolicyComparisonSeverity,
    PolicyRuleComparisonKind,
)
from app.services.policy_rule_comparison import (
    compare_policy_rule_sets,
)


LEFT_DOCUMENT_VERSION_ID = uuid4()
RIGHT_DOCUMENT_VERSION_ID = uuid4()


def make_rule(
    *,
    rule_key: str,
    value: object,
    conditions: dict[str, object],
    source_quote: str,
    effective_at: datetime | None = None,
    expires_at: datetime | None = None,
) -> PolicyRule:
    """Build one in-memory policy rule."""

    return PolicyRule(
        id=uuid4(),
        document_version_id=uuid4(),
        rule_key=rule_key,
        value=value,
        conditions=conditions,
        source_quote=source_quote,
        effective_at=effective_at,
        expires_at=expires_at,
        confidence=0.95,
    )


def test_new_rule_in_right_version_is_update() -> None:
    """A rule only present in the newer version is an update."""

    left_rules: list[PolicyRule] = []

    new_free_return_rule = make_rule(
        rule_key="refund.member_free_return_tier",
        value="gold",
        conditions={
            "includes": "platinum",
        },
        source_quote="金卡及以上会员享受指定商品免费退货。",
    )
    right_rules = [
        new_free_return_rule,
    ]

    comparisons = compare_policy_rule_sets(
        left_rules=left_rules,
        right_rules=right_rules,
        left_document_version_id=LEFT_DOCUMENT_VERSION_ID,
        right_document_version_id=RIGHT_DOCUMENT_VERSION_ID,
    )

    assert len(comparisons) == 1

    comparison = comparisons[0]

    assert comparison.kind is PolicyRuleComparisonKind.UPDATE
    assert comparison.severity is PolicyComparisonSeverity.LOW
    assert comparison.left_rule_id is None
    assert comparison.right_rule_id == new_free_return_rule.id
    assert (
        comparison.left_document_version_id
        == LEFT_DOCUMENT_VERSION_ID
    )
    assert (
        comparison.right_document_version_id
        == RIGHT_DOCUMENT_VERSION_ID
    )
    assert comparison.rule_key.value == (
        "refund.member_free_return_tier"
    )
    assert comparison.evidence == [
        new_free_return_rule.source_quote,
    ]


def test_existing_matching_rules_are_compared() -> None:
    """Rules existing in both versions should use rule comparison."""

    left_rule = make_rule(
        rule_key="refund.window_days",
        value=7,
        conditions={
            "membership_tier": "standard",
        },
        source_quote="v1：普通会员退款期限为 7 天。",
        effective_at=datetime(
            2025,
            1,
            1,
            tzinfo=UTC,
        ),
        expires_at=datetime(
            2025,
            4,
            1,
            tzinfo=UTC,
        ),
    )
    right_rule = make_rule(
        rule_key="refund.window_days",
        value=15,
        conditions={
            "membership_tier": "standard",
        },
        source_quote="v3：普通会员退款期限为 15 天。",
        effective_at=datetime(
            2025,
            7,
            1,
            tzinfo=UTC,
        ),
        expires_at=None,
    )

    comparisons = compare_policy_rule_sets(
        left_rules=[left_rule],
        right_rules=[right_rule],
        left_document_version_id=LEFT_DOCUMENT_VERSION_ID,
        right_document_version_id=RIGHT_DOCUMENT_VERSION_ID,
    )

    assert len(comparisons) == 1
    assert (
        comparisons[0].kind
        is PolicyRuleComparisonKind.HISTORICAL_DIFFERENCE
    )


def test_removed_rule_is_not_silently_ignored() -> None:
    """A rule only in the old version must fail explicitly for now."""

    removed_rule = make_rule(
        rule_key="refund.window_days",
        value=7,
        conditions={
            "membership_tier": "standard",
        },
        source_quote="旧版本规则。",
    )

    with pytest.raises(
        NotImplementedError,
        match="Removed policy rules are not implemented yet.",
    ):
        compare_policy_rule_sets(
            left_rules=[removed_rule],
            right_rules=[],
            left_document_version_id=LEFT_DOCUMENT_VERSION_ID,
            right_document_version_id=RIGHT_DOCUMENT_VERSION_ID,
        )


def test_duplicate_match_keys_are_rejected() -> None:
    """Duplicate rule keys and conditions must not overwrite each other."""

    first_rule = make_rule(
        rule_key="refund.window_days",
        value=15,
        conditions={
            "membership_tier": "gold",
        },
        source_quote="第一条 gold 规则。",
    )
    duplicate_rule = make_rule(
        rule_key="refund.window_days",
        value=20,
        conditions={
            "membership_tier": "gold",
        },
        source_quote="第二条 gold 规则。",
    )

    with pytest.raises(
        ValueError,
        match=(
            "Duplicate policy rules have the same "
            "rule key and conditions."
        ),
    ):
        compare_policy_rule_sets(
            left_rules=[
                first_rule,
                duplicate_rule,
            ],
            right_rules=[],
            left_document_version_id=LEFT_DOCUMENT_VERSION_ID,
            right_document_version_id=RIGHT_DOCUMENT_VERSION_ID,
        )


def test_new_high_risk_rule_is_not_classified_as_normal_update() -> None:
    """A newly added unlimited rule should be high-risk."""

    risky_rule = make_rule(
        rule_key="refund.window_days",
        value="unlimited",
        conditions={},
        source_quote="运营通知：所有商品永久支持退款。",
    )

    comparisons = compare_policy_rule_sets(
        left_rules=[],
        right_rules=[risky_rule],
        left_document_version_id=LEFT_DOCUMENT_VERSION_ID,
        right_document_version_id=RIGHT_DOCUMENT_VERSION_ID,
    )

    assert len(comparisons) == 1
    assert (
        comparisons[0].kind
        is PolicyRuleComparisonKind.HIGH_RISK_ERROR
    )
    assert (
        comparisons[0].severity
        is PolicyComparisonSeverity.HIGH
    )