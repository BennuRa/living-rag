"""Persist real refund policy comparisons into the database."""

from sqlalchemy import select

from app.core.database import SessionLocal
from app.models.document import Document, DocumentVersion
from app.models.policy_conflict import PolicyConflict
from app.models.policy_rule import PolicyRule
from app.services.policy_conflict_service import (
    persist_policy_comparisons,
)
from app.services.policy_rule_comparison import (
    compare_policy_rule_sets,
)


def load_document_version(
    db,
    *,
    policy_key: str,
    version_number: int,
) -> DocumentVersion:
    """Load one document version by policy key and version number."""

    statement = (
        select(DocumentVersion)
        .join(Document)
        .where(
            Document.policy_key == policy_key,
            DocumentVersion.version_number == version_number,
        )
    )

    return db.scalars(statement).one()


def load_policy_rules(
    db,
    document_version_id,
):
    """Load all structured rules belonging to one document version."""

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

    return list(db.scalars(statement).all())


def main() -> None:
    """Compare refund policy v1 and v3 and persist the results."""

    db = SessionLocal()

    try:
        left_version = load_document_version(
            db,
            policy_key="REFUND-POLICY",
            version_number=1,
        )
        right_version = load_document_version(
            db,
            policy_key="REFUND-POLICY",
            version_number=3,
        )

        left_rules = load_policy_rules(
            db,
            left_version.id,
        )
        right_rules = load_policy_rules(
            db,
            right_version.id,
        )

        print(
            f"left_version={left_version.version_number} "
            f"left_rules={len(left_rules)}"
        )
        print(
            f"right_version={right_version.version_number} "
            f"right_rules={len(right_rules)}"
        )

        comparisons = compare_policy_rule_sets(
            left_rules=left_rules,
            right_rules=right_rules,
            left_document_version_id=left_version.id,
            right_document_version_id=right_version.id,
        )

        print(
            f"comparisons={len(comparisons)}"
        )

        existing_statement = select(PolicyConflict).where(
            PolicyConflict.left_document_version_id == left_version.id,
            PolicyConflict.right_document_version_id == right_version.id,
        )

        existing_conflicts = db.scalars(existing_statement).all()

        if existing_conflicts:
            print(
                "comparisons_already_persisted="
                f"{len(existing_conflicts)}"
            )
            return

        persisted_conflicts = persist_policy_comparisons(
            db,
            comparisons,
        )

        db.commit()

        print(
            "saved_conflicts="
            f"{len(persisted_conflicts)}"
        )

        for conflict in persisted_conflicts:
            print(
                conflict.kind,
                conflict.severity,
                conflict.rule_key,
                conflict.status,
            )

    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()