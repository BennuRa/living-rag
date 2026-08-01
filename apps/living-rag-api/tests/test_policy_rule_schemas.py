"""Tests for structured policy rule schemas."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas.policy_rule import (
    PolicyRuleExtraction,
    PolicyRuleKey,
)


def test_policy_rule_extraction_accepts_valid_refund_window() -> None:
    """A valid refund window rule should pass Pydantic validation."""

    document_version_id = uuid4()

    rule = PolicyRuleExtraction(
        rule_key=PolicyRuleKey.REFUND_WINDOW_DAYS,
        value=7,
        conditions={"membership_tier": "standard"},
        source_quote="普通会员签收后 7 个自然日内可以申请退款。",
        document_version_id=document_version_id,
        effective_at=datetime(2025, 1, 1, tzinfo=UTC),
        expires_at=datetime(2025, 3, 31, tzinfo=UTC),
        confidence=0.95,
    )

    assert rule.rule_key is PolicyRuleKey.REFUND_WINDOW_DAYS
    assert rule.value == 7
    assert rule.conditions == {"membership_tier": "standard"}
    assert rule.source_quote
    assert rule.document_version_id == document_version_id
    assert rule.confidence == 0.95


def test_policy_rule_extraction_rejects_unknown_rule_key() -> None:
    """An unknown rule key must be rejected."""

    with pytest.raises(ValidationError):
        PolicyRuleExtraction(
            rule_key="refund.unknown_rule",
            value=7,
            source_quote="未知规则。",
            document_version_id=uuid4(),
            confidence=0.8,
        )


def test_policy_rule_extraction_rejects_confidence_out_of_range() -> None:
    """Confidence must stay within the inclusive range [0, 1]."""

    with pytest.raises(ValidationError):
        PolicyRuleExtraction(
            rule_key=PolicyRuleKey.REFUND_WINDOW_DAYS,
            value=7,
            source_quote="普通会员签收后 7 个自然日内可以申请退款。",
            document_version_id=uuid4(),
            confidence=1.1,
        )