"""Tests for policy rule condition overlap detection."""

from app.services.policy_rule_comparison import _conditions_overlap


def test_empty_conditions_overlap_with_empty_conditions() -> None:
    """Two unrestricted rules may apply to the same cases."""

    assert _conditions_overlap(
        {},
        {},
    )


def test_empty_conditions_overlap_with_specific_conditions() -> None:
    """An unrestricted rule overlaps with a narrower conditional rule."""

    assert _conditions_overlap(
        {},
        {"campaign": "double_11"},
    )

    assert _conditions_overlap(
        {"campaign": "double_11"},
        {},
    )


def test_same_condition_values_overlap() -> None:
    """Rules with identical shared conditions overlap."""

    assert _conditions_overlap(
        {"membership_tier": "gold"},
        {"membership_tier": "gold"},
    )


def test_different_values_for_same_condition_do_not_overlap() -> None:
    """Contradictory values for one condition key do not overlap."""

    assert not _conditions_overlap(
        {"membership_tier": "gold"},
        {"membership_tier": "silver"},
    )


def test_different_condition_keys_may_overlap() -> None:
    """Independent condition dimensions may be true at the same time."""

    assert _conditions_overlap(
        {"membership_tier": "gold"},
        {"campaign": "double_11"},
    )


def test_multiple_shared_conditions_must_all_match() -> None:
    """One mismatching shared condition makes the sets disjoint."""

    assert not _conditions_overlap(
        {
            "membership_tier": "gold",
            "campaign": "double_11",
        },
        {
            "membership_tier": "gold",
            "campaign": "618",
        },
    )