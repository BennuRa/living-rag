from sqlalchemy import select

from app.core.database import SessionLocal
from app.models.document import Document, DocumentVersion
from app.services.policy_rule_service import (
    replace_policy_rules_for_document_version,
)


def main() -> None:
    db = SessionLocal()

    try:
        statement = (
            select(DocumentVersion)
            .join(Document)
            .where(
                Document.policy_key == "REFUND-POLICY",
                DocumentVersion.version_number == 3,
            )
        )

        document_version = db.scalars(statement).one()

        rules = replace_policy_rules_for_document_version(
            db,
            document_version,
        )

        db.commit()

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


if __name__ == "__main__":
    main()