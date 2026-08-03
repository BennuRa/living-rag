"""Persist structured policy rules for one document version."""

import argparse

from sqlalchemy import select

from app.core.database import SessionLocal
from app.models.document import Document, DocumentVersion
from app.services.policy_rule_service import (
    replace_policy_rules_for_document_version,
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


def persist_policy_rules(
    *,
    policy_key: str,
    version_number: int,
) -> None:
    """Extract and persist rules for one document version."""

    db = SessionLocal()

    try:
        document_version = load_document_version(
            db,
            policy_key=policy_key,
            version_number=version_number,
        )

        rules = replace_policy_rules_for_document_version(
            db,
            document_version,
        )

        db.commit()

        print(
            f"policy_key={policy_key} "
            f"version_number={version_number}"
        )
        print(f"saved_rules={len(rules)}")

        for rule in rules:
            print(
                rule.rule_key,
                rule.value,
                rule.conditions,
            )

    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""

    parser = argparse.ArgumentParser(
        description=(
            "Extract and persist policy rules for one document version."
        ),
    )

    parser.add_argument(
        "--policy-key",
        default="REFUND-POLICY",
        help="Policy key to process.",
    )

    parser.add_argument(
        "--version",
        type=int,
        required=True,
        help="Document version number to process.",
    )

    return parser.parse_args()


def main() -> None:
    """Run the policy rule persistence command."""

    args = parse_args()

    persist_policy_rules(
        policy_key=args.policy_key,
        version_number=args.version,
    )


if __name__ == "__main__":
    main()