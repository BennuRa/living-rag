"""Tests for policy rule condition specificity."""

from app.services.policy_rule_comparison import (
    _is_strictly_more_specific,
)


def test_specific_campaign_condition_is_narrower_than_empty_condition(
) -> None:
    """A campaign-specific rule is narrower than an unrestricted rule."""

    assert _is_strictly_more_specific(
        broad_conditions={},
        narrow_conditions={
            "campaign": "double_11",
        },
    )


def test_extra_condition_makes_rule_more_specific() -> None:
    """An additional matching condition narrows the applicable scope."""

    assert _is_strictly_more_specific(
        broad_conditions={
            "membership_tier": "gold",
        },
        narrow_conditions={
            "membership_tier": "gold",
            "campaign": "double_11",
        },
    )


def test_same_conditions_are_not_strictly_more_specific() -> None:
    """Identical conditions do not form a strict specificity relationship."""

    assert not _is_strictly_more_specific(
        broad_conditions={
            "membership_tier": "gold",
        },
        narrow_conditions={
            "membership_tier": "gold",
        },
    )


def test_reversed_specificity_is_false() -> None:
    """A broad condition set cannot be narrower than an empty set."""

    assert not _is_strictly_more_specific(
        broad_conditions={
            "campaign": "double_11",
        },
        narrow_conditions={},
    )


def test_missing_broad_condition_is_not_specificity() -> None:
    """Different condition dimensions do not create containment."""

    assert not _is_strictly_more_specific(
        broad_conditions={
            "membership_tier": "gold",
            "region": "east",
        },
        narrow_conditions={
            "membership_tier": "gold",
            "campaign": "double_11",
        },
    )


def test_different_shared_condition_value_is_not_specificity() -> None:
    """A changed shared value is not a narrower version of the rule."""

    assert not _is_strictly_more_specific(
        broad_conditions={
            "membership_tier": "gold",
        },
        narrow_conditions={
            "membership_tier": "silver",
            "campaign": "double_11",
        },
    )