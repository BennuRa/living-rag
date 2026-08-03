"""Tests for policy rule comparison foundations."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.models.policy_rule import PolicyRule
from app.schemas.policy_comparison import (
    PolicyComparisonSeverity,
    PolicyRuleComparisonKind,
)
from app.services.policy_rule_comparison import (
    _rules_have_overlapping_period,
    compare_policy_rules,
)


def make_rule(
    *,
    rule_key: str = "refund.window_days",
    effective_at: datetime | None,
    expires_at: datetime | None,
    value: object = 15,
) -> PolicyRule:
    """Build one in-memory policy rule for comparison tests."""

    return PolicyRule(
        id=uuid4(),
        document_version_id=uuid4(),
        rule_key=rule_key,
        value=value,
        conditions={},
        source_quote="test source quote",
        effective_at=effective_at,
        expires_at=expires_at,
        confidence=0.95,
    )


def test_rules_with_adjacent_periods_do_not_overlap() -> None:
    """A rule ending when another starts is not overlapping."""

    left_rule = make_rule(
        effective_at=datetime(2025, 1, 1, tzinfo=UTC),
        expires_at=datetime(2025, 4, 1, tzinfo=UTC),
    )
    right_rule = make_rule(
        effective_at=datetime(2025, 4, 1, tzinfo=UTC),
        expires_at=datetime(2025, 7, 1, tzinfo=UTC),
    )

    assert (
        _rules_have_overlapping_period(
            left_rule,
            right_rule,
        )
        is False
    )


def test_rules_do_not_overlap_when_right_rule_ends_before_left_rule() -> None:
    """The reverse non-overlap order should also be detected."""

    left_rule = make_rule(
        effective_at=datetime(2025, 7, 1, tzinfo=UTC),
        expires_at=datetime(2025, 10, 1, tzinfo=UTC),
    )
    right_rule = make_rule(
        effective_at=datetime(2025, 1, 1, tzinfo=UTC),
        expires_at=datetime(2025, 7, 1, tzinfo=UTC),
    )

    assert (
        _rules_have_overlapping_period(
            left_rule,
            right_rule,
        )
        is False
    )


def test_rules_with_overlapping_periods_return_true() -> None:
    """Partially overlapping effective periods should return True."""

    left_rule = make_rule(
        effective_at=datetime(2025, 1, 1, tzinfo=UTC),
        expires_at=datetime(2025, 5, 1, tzinfo=UTC),
    )
    right_rule = make_rule(
        effective_at=datetime(2025, 4, 1, tzinfo=UTC),
        expires_at=datetime(2025, 7, 1, tzinfo=UTC),
    )

    assert _rules_have_overlapping_period(
        left_rule,
        right_rule,
    )


def test_rules_without_expiration_are_treated_as_open_ended() -> None:
    """A missing expires_at means the rule continues indefinitely."""

    left_rule = make_rule(
        effective_at=datetime(2025, 7, 1, tzinfo=UTC),
        expires_at=None,
    )
    right_rule = make_rule(
        effective_at=datetime(2025, 1, 1, tzinfo=UTC),
        expires_at=None,
    )

    assert _rules_have_overlapping_period(
        left_rule,
        right_rule,
    )


def test_different_rule_keys_raise_value_error() -> None:
    """Rules with different semantic keys cannot be compared."""

    left_rule = make_rule(
        rule_key="refund.window_days",
        effective_at=datetime(2025, 1, 1, tzinfo=UTC),
        expires_at=None,
    )
    right_rule = make_rule(
        rule_key="refund.member_free_return_tier",
        effective_at=datetime(2025, 1, 1, tzinfo=UTC),
        expires_at=None,
        value="gold",
    )

    with pytest.raises(
        ValueError,
        match="Cannot compare rules with different rule keys.",
    ):
        compare_policy_rules(
            left_rule,
            right_rule,
        )


def test_same_rule_key_with_overlapping_periods_returns_conflict() -> None:
    """Same-key rules with overlapping periods and different values conflict."""

    left_rule = make_rule(
        rule_key="refund.window_days",
        effective_at=datetime(2025, 1, 1, tzinfo=UTC),
        expires_at=None,
        value=7,
    )
    right_rule = make_rule(
        rule_key="refund.window_days",
        effective_at=datetime(2025, 7, 1, tzinfo=UTC),
        expires_at=None,
        value=15,
    )

    comparison = compare_policy_rules(
        left_rule,
        right_rule,
    )

    assert comparison.kind == PolicyRuleComparisonKind.CONFLICT
    assert comparison.severity == PolicyComparisonSeverity.HIGH
    assert comparison.rule_key == "refund.window_days"
    assert comparison.left_rule_id == left_rule.id
    assert comparison.right_rule_id == right_rule.id
    assert (
        comparison.left_document_version_id
        == left_rule.document_version_id
    )
    assert (
        comparison.right_document_version_id
        == right_rule.document_version_id
    )
    assert comparison.reason
    assert comparison.recommended_action
    assert comparison.evidence == [
        left_rule.source_quote,
        right_rule.source_quote,
    ]