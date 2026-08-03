"""Tests for historical policy rule comparison."""

from datetime import UTC, datetime
from uuid import uuid4

from app.models.policy_rule import PolicyRule
from app.services.policy_rule_comparison import compare_policy_rules
from app.schemas.policy_comparison import (
    PolicyComparisonSeverity,
    PolicyRuleComparisonKind,
)


def make_rule(
    *,
    effective_at: datetime,
    expires_at: datetime | None,
    value: object,
    source_quote: str,
) -> PolicyRule:
    """Build one in-memory policy rule for comparison tests."""

    return PolicyRule(
        id=uuid4(),
        document_version_id=uuid4(),
        rule_key="refund.window_days",
        value=value,
        conditions={
            "membership_tier": "standard",
        },
        source_quote=source_quote,
        effective_at=effective_at,
        expires_at=expires_at,
        confidence=0.95,
    )


def test_non_overlapping_rules_are_historical_difference() -> None:
    """Rules from separate periods should not become a conflict."""

    first_rule = make_rule(
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
        value=7,
        source_quote="Refund within 7 days.",
    )
    latest_rule = make_rule(
        effective_at=datetime(
            2025,
            7,
            1,
            tzinfo=UTC,
        ),
        expires_at=None,
        value=15,
        source_quote="Refund within 15 days.",
    )

    comparison = compare_policy_rules(
        first_rule,
        latest_rule,
    )

    assert (
        comparison.kind
        is PolicyRuleComparisonKind.HISTORICAL_DIFFERENCE
    )
    assert comparison.severity is PolicyComparisonSeverity.LOW
    assert comparison.rule_key.value == "refund.window_days"

    assert comparison.left_rule_id == first_rule.id
    assert comparison.right_rule_id == latest_rule.id
    assert (
        comparison.left_document_version_id
        == first_rule.document_version_id
    )
    assert (
        comparison.right_document_version_id
        == latest_rule.document_version_id
    )

    assert comparison.reason
    assert comparison.recommended_action
    assert comparison.evidence == [
        first_rule.source_quote,
        latest_rule.source_quote,
    ]


def test_adjacent_version_periods_are_not_a_conflict() -> None:
    """A rule ending when the next rule starts is historical, not conflicting."""

    first_rule = make_rule(
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
        value=7,
        source_quote="Version 1: 7 days.",
    )
    next_rule = make_rule(
        effective_at=datetime(
            2025,
            4,
            1,
            tzinfo=UTC,
        ),
        expires_at=None,
        value=10,
        source_quote="Version 2: 10 days.",
    )

    comparison = compare_policy_rules(
        first_rule,
        next_rule,
    )

    assert (
        comparison.kind
        is PolicyRuleComparisonKind.HISTORICAL_DIFFERENCE
    )
    assert comparison.severity is PolicyComparisonSeverity.LOW
    assert comparison.evidence == [
        first_rule.source_quote,
        next_rule.source_quote,
    ]