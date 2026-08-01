"""Tests for idempotent policy rule persistence."""

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import select

from app.models.document import (
    Document,
    DocumentGovernanceStatus,
    DocumentSourceType,
    DocumentVersion,
    DocumentVersionStatus,
)
from app.models.policy_rule import PolicyRule
from app.services.policy_rule_service import (
    replace_policy_rules_for_document_version,
)


TEST_EFFECTIVE_AT = datetime(
    2025,
    7,
    1,
    tzinfo=UTC,
)


TEST_POLICY_CONTENT = """
## Refund Policy V3

| standard | 7 natural days |
| silver | 10 natural days |
| gold | 15 natural days |
| platinum | 20 natural days |

Gold and platinum members can receive platform-paid return shipping.
"""


def create_document_version(
    db_session,
    *,
    version_number: int,
    content: str = TEST_POLICY_CONTENT,
) -> DocumentVersion:
    """Create one persisted document and one persisted document version."""

    document = Document(
        title="会员退款政策",
        policy_key=f"POLICY-RULE-TEST-{uuid4()}",
        domain="refund",
    )
    db_session.add(document)
    db_session.flush()

    document_version = DocumentVersion(
        document_id=document.id,
        version_number=version_number,
        status=DocumentVersionStatus.READY,
        source_type=DocumentSourceType.OFFICIAL_POLICY,
        governance_status=DocumentGovernanceStatus.ACTIVE,
        effective_at=TEST_EFFECTIVE_AT,
        expires_at=None,
        content=content,
        content_hash=f"{version_number:064d}",
    )
    db_session.add(document_version)
    db_session.flush()

    return document_version


def get_rules_for_version(
    db_session,
    document_version_id,
) -> list[PolicyRule]:
    """Return all persisted rules belonging to one document version."""

    statement = (
        select(PolicyRule)
        .where(
            PolicyRule.document_version_id == document_version_id,
        )
        .order_by(
            PolicyRule.rule_key,
            PolicyRule.id,
        )
    )

    return list(db_session.scalars(statement).all())


def test_replace_policy_rules_persists_extracted_rules(
    db_session,
) -> None:
    """One document version should persist all extracted structured rules."""

    document_version = create_document_version(
        db_session,
        version_number=3,
    )

    persisted_rules = replace_policy_rules_for_document_version(
        db_session,
        document_version,
    )

    stored_rules = get_rules_for_version(
        db_session,
        document_version.id,
    )

    assert len(persisted_rules) == 5
    assert len(stored_rules) == 5

    window_rules = {
        rule.conditions["membership_tier"]: rule.value
        for rule in stored_rules
        if rule.rule_key == "refund.window_days"
    }

    assert window_rules == {
        "standard": 7,
        "silver": 10,
        "gold": 15,
        "platinum": 20,
    }

    free_return_rules = [
        rule
        for rule in stored_rules
        if rule.rule_key == "refund.member_free_return_tier"
    ]

    assert len(free_return_rules) == 1

    free_return_rule = free_return_rules[0]

    assert free_return_rule.value == "gold"
    assert free_return_rule.conditions == {
        "includes": "platinum",
    }

    for rule in stored_rules:
        assert rule.document_version_id == document_version.id
        assert rule.effective_at == document_version.effective_at
        assert rule.expires_at == document_version.expires_at
        assert rule.source_quote
        assert 0.0 <= rule.confidence <= 1.0


def test_replace_policy_rules_is_idempotent(
    db_session,
) -> None:
    """Repeating the replacement must not duplicate rules."""

    document_version = create_document_version(
        db_session,
        version_number=3,
    )

    first_result = replace_policy_rules_for_document_version(
        db_session,
        document_version,
    )
    first_ids = {
        rule.id
        for rule in get_rules_for_version(
            db_session,
            document_version.id,
        )
    }

    second_result = replace_policy_rules_for_document_version(
        db_session,
        document_version,
    )
    stored_rules = get_rules_for_version(
        db_session,
        document_version.id,
    )

    assert len(first_result) == 5
    assert len(second_result) == 5
    assert len(stored_rules) == 5

    second_ids = {
        rule.id
        for rule in stored_rules
    }

    assert first_ids.isdisjoint(second_ids)


def test_replacing_one_version_does_not_delete_other_version_rules(
    db_session,
) -> None:
    """Refreshing one document version must preserve another version's rules."""

    first_version = create_document_version(
        db_session,
        version_number=1,
    )
    second_version = create_document_version(
        db_session,
        version_number=2,
    )

    replace_policy_rules_for_document_version(
        db_session,
        first_version,
    )
    replace_policy_rules_for_document_version(
        db_session,
        second_version,
    )

    first_version_rules_before_refresh = get_rules_for_version(
        db_session,
        first_version.id,
    )

    replace_policy_rules_for_document_version(
        db_session,
        second_version,
    )

    first_version_rules_after_refresh = get_rules_for_version(
        db_session,
        first_version.id,
    )
    second_version_rules_after_refresh = get_rules_for_version(
        db_session,
        second_version.id,
    )

    assert len(first_version_rules_before_refresh) == 5
    assert len(first_version_rules_after_refresh) == 5
    assert len(second_version_rules_after_refresh) == 5

    assert {
        rule.id
        for rule in first_version_rules_before_refresh
    } == {
        rule.id
        for rule in first_version_rules_after_refresh
    }