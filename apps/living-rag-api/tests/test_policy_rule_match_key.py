"""Tests for stable policy rule matching keys."""

from uuid import uuid4

from app.models.policy_rule import PolicyRule
from app.services.policy_rule_comparison import _rule_match_key


def make_rule(
    *,
    rule_key: str,
    conditions: dict[str, object],
) -> PolicyRule:
    """Build one in-memory rule for match-key tests."""

    return PolicyRule(
        id=uuid4(),
        document_version_id=uuid4(),
        rule_key=rule_key,
        value=15,
        conditions=conditions,
        source_quote="test source quote",
        effective_at=None,
        expires_at=None,
        confidence=0.95,
    )


def test_same_conditions_with_different_order_have_same_key() -> None:
    """Condition insertion order must not affect matching."""

    first_rule = make_rule(
        rule_key="refund.window_days",
        conditions={
            "membership_tier": "gold",
            "campaign": "double_11",
        },
    )
    second_rule = make_rule(
        rule_key="refund.window_days",
        conditions={
            "campaign": "double_11",
            "membership_tier": "gold",
        },
    )

    assert _rule_match_key(first_rule) == _rule_match_key(second_rule)


def test_same_rule_key_with_different_conditions_has_different_key() -> None:
    """Different conditions identify different rules."""

    standard_rule = make_rule(
        rule_key="refund.window_days",
        conditions={
            "membership_tier": "standard",
        },
    )
    gold_rule = make_rule(
        rule_key="refund.window_days",
        conditions={
            "membership_tier": "gold",
        },
    )

    assert _rule_match_key(standard_rule) != _rule_match_key(gold_rule)


def test_different_rule_keys_have_different_match_keys() -> None:
    """Different semantic rule keys must not match."""

    window_rule = make_rule(
        rule_key="refund.window_days",
        conditions={
            "membership_tier": "gold",
        },
    )
    free_return_rule = make_rule(
        rule_key="refund.member_free_return_tier",
        conditions={
            "membership_tier": "gold",
        },
    )

    assert _rule_match_key(window_rule) != _rule_match_key(
        free_return_rule,
    )


def test_empty_conditions_have_stable_match_key() -> None:
    """An empty condition mapping should still produce a stable key."""

    first_rule = make_rule(
        rule_key="refund.window_days",
        conditions={},
    )
    second_rule = make_rule(
        rule_key="refund.window_days",
        conditions={},
    )

    first_key = _rule_match_key(first_rule)
    second_key = _rule_match_key(second_rule)

    assert first_key == second_key
    assert first_key[0] == "refund.window_days"
    assert first_key[1] == "{}"


def test_nested_json_conditions_are_order_independent() -> None:
    """Nested JSON condition objects should be normalized by key order."""

    first_rule = make_rule(
        rule_key="refund.window_days",
        conditions={
            "eligibility": {
                "tier": "gold",
                "region": "east",
            },
        },
    )
    second_rule = make_rule(
        rule_key="refund.window_days",
        conditions={
            "eligibility": {
                "region": "east",
                "tier": "gold",
            },
        },
    )

    assert _rule_match_key(first_rule) == _rule_match_key(second_rule)