"""Persistence service for structured policy rules."""

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.models.document import DocumentVersion
from app.models.policy_rule import PolicyRule
from app.services.policy_rule_extraction import extract_policy_rules


def replace_policy_rules_for_document_version(
    db: Session,
    document_version: DocumentVersion,
) -> list[PolicyRule]:
    """Replace all extracted rules belonging to one document version."""

    extractions = extract_policy_rules(document_version)

    delete_statement = delete(PolicyRule).where(
        PolicyRule.document_version_id == document_version.id,
    )
    db.execute(delete_statement)

    persisted_rules: list[PolicyRule] = []

    for extraction in extractions:
        rule = PolicyRule(
            document_version_id=document_version.id,
            rule_key=extraction.rule_key.value,
            value=extraction.value,
            conditions=extraction.conditions,
            source_quote=extraction.source_quote,
            effective_at=extraction.effective_at,
            expires_at=extraction.expires_at,
            confidence=extraction.confidence,
        )
        persisted_rules.append(rule)

    db.add_all(persisted_rules)
    db.flush()

    return persisted_rules