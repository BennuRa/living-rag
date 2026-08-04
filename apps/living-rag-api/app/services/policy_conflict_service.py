"""Persistence service for policy comparison results."""

from sqlalchemy.orm import Session

from app.models.policy_conflict import (
    ConflictEvidence,
    PolicyConflict,
)
from app.schemas.policy_comparison import PolicyRuleComparison
from app.services.review_task_service import (
    create_review_tasks_for_open_conflicts,
)


def persist_policy_comparison(
    db: Session,
    comparison: PolicyRuleComparison,
) -> PolicyConflict:
    """Persist one policy comparison and create review tasks when needed."""

    conflict = PolicyConflict(
        kind=comparison.kind.value,
        severity=comparison.severity.value,
        rule_key=comparison.rule_key.value,
        left_rule_id=comparison.left_rule_id,
        right_rule_id=comparison.right_rule_id,
        left_document_version_id=comparison.left_document_version_id,
        right_document_version_id=comparison.right_document_version_id,
        reason=comparison.reason,
        recommended_action=comparison.recommended_action,
    )

    db.add(conflict)
    db.flush()

    evidence_rows: list[ConflictEvidence] = []

    for position, quote in enumerate(comparison.evidence):
        is_right_only_update = (
            comparison.left_rule_id is None
            and comparison.right_rule_id is not None
        )

        if is_right_only_update:
            evidence_rule_id = comparison.right_rule_id
            evidence_version_id = (
                comparison.right_document_version_id
            )
        elif position == 0:
            evidence_rule_id = comparison.left_rule_id
            evidence_version_id = (
                comparison.left_document_version_id
            )
        else:
            evidence_rule_id = comparison.right_rule_id
            evidence_version_id = (
                comparison.right_document_version_id
            )

        evidence_rows.append(
            ConflictEvidence(
                conflict_id=conflict.id,
                rule_id=evidence_rule_id,
                document_version_id=evidence_version_id,
                quote=quote,
                position=position,
            )
        )

    db.add_all(evidence_rows)
    db.flush()

    create_review_tasks_for_open_conflicts(db)

    return conflict


def persist_policy_comparisons(
    db: Session,
    comparisons: list[PolicyRuleComparison],
) -> list[PolicyConflict]:
    """Persist multiple comparisons and create review tasks."""

    persisted_conflicts: list[PolicyConflict] = []

    for comparison in comparisons:
        persisted_conflicts.append(
            persist_policy_comparison(
                db,
                comparison,
            )
        )

    return persisted_conflicts