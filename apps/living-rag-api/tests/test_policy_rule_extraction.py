"""Tests for deterministic structured policy rule extraction."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.models.document import DocumentVersion
from app.schemas.policy_rule import PolicyRuleKey
from app.services.policy_rule_extraction import extract_policy_rules


TEST_EFFECTIVE_AT = datetime(
    2025,
    7,
    1,
    tzinfo=UTC,
)


def make_document_version(
    content: str,
) -> DocumentVersion:
    """Build one in-memory document version for extraction tests."""

    return DocumentVersion(
        id=uuid4(),
        document_id=uuid4(),
        version_number=3,
        content=content,
        content_hash="a" * 64,
        effective_at=TEST_EFFECTIVE_AT,
        expires_at=None,
    )


def test_extract_policy_rules_returns_membership_windows_and_free_return_rule(
) -> None:
    """Extract four membership windows and one free-return tier rule."""

    content = """
## Refund Policy V3

| standard | 7 natural days |
| silver | 10 natural days |
| gold | 15 natural days |
| platinum | 20 natural days |

Gold and platinum members can receive platform-paid return shipping.
"""

    document_version = make_document_version(content)

    rules = extract_policy_rules(document_version)

    window_rules = {
        rule.conditions["membership_tier"]: rule.value
        for rule in rules
        if rule.rule_key is PolicyRuleKey.REFUND_WINDOW_DAYS
    }

    free_return_rules = [
        rule
        for rule in rules
        if rule.rule_key
        is PolicyRuleKey.REFUND_MEMBER_FREE_RETURN_TIER
    ]

    assert window_rules == {
        "standard": 7,
        "silver": 10,
        "gold": 15,
        "platinum": 20,
    }

    assert len(free_return_rules) == 1

    free_return_rule = free_return_rules[0]

    assert free_return_rule.value == "gold"
    assert free_return_rule.conditions == {
        "includes": "platinum",
    }

    for rule in rules:
        assert rule.document_version_id == document_version.id
        assert rule.effective_at == document_version.effective_at
        assert rule.expires_at == document_version.expires_at
        assert rule.source_quote
        assert 0.0 <= rule.confidence <= 1.0


def test_extract_policy_rules_does_not_duplicate_free_return_rule() -> None:
    """Multiple matching evidence lines should produce one free-return rule."""

    content = """
| standard | 7 natural days |
| silver | 10 natural days |
| gold | 15 natural days |
| platinum | 20 natural days |

Gold and platinum members receive platform-paid return shipping.
Gold and platinum members receive the same benefit for designated products.
"""

    document_version = make_document_version(content)

    rules = extract_policy_rules(document_version)

    free_return_rules = [
        rule
        for rule in rules
        if rule.rule_key
        is PolicyRuleKey.REFUND_MEMBER_FREE_RETURN_TIER
    ]

    assert len(free_return_rules) == 1


def test_extract_policy_rules_rejects_content_without_membership_window_table(
) -> None:
    """Missing membership-window evidence must fail explicitly."""

    content = """
## Refund Policy

This document contains no membership refund window table.
"""

    document_version = make_document_version(content)

    with pytest.raises(
        ValueError,
        match="Refund membership window table was not found.",
    ):
        extract_policy_rules(document_version)