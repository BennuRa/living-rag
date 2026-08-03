"""Persist Day 10 real-document comparison acceptance cases."""

from sqlalchemy import select

from app.core.database import SessionLocal
from app.models.document import Document, DocumentVersion
from app.models.policy_conflict import PolicyConflict
from app.models.policy_rule import PolicyRule
from app.services.policy_conflict_service import persist_policy_comparison
from app.services.policy_rule_comparison import compare_policy_rules


def load_version(
    db,
    policy_key: str,
    version_number: int = 1,
) -> DocumentVersion:
    """Load one document version for an acceptance document."""

    statement = (
        select(DocumentVersion)
        .join(Document)
        .where(
            Document.policy_key == policy_key,
            DocumentVersion.version_number == version_number,
        )
    )
    return db.scalars(statement).one()


def find_or_create_rule(
    db,
    version: DocumentVersion,
    *,
    value: object,
    conditions: dict[str, object],
    source_quote: str,
) -> PolicyRule:
    """Create one deterministic acceptance rule if it is missing."""

    statement = select(PolicyRule).where(
        PolicyRule.document_version_id == version.id,
        PolicyRule.rule_key == "refund.window_days",
    )

    for existing in db.scalars(statement).all():
        if existing.value == value and existing.conditions == conditions:
            return existing

    rule = PolicyRule(
        document_version_id=version.id,
        rule_key="refund.window_days",
        value=value,
        conditions=conditions,
        source_quote=source_quote,
        effective_at=version.effective_at,
        expires_at=version.expires_at,
        confidence=0.95,
    )
    db.add(rule)
    db.flush()
    return rule


def persist_comparison_once(db, left_rule, right_rule) -> None:
    """Persist one comparison unless the same pair already exists."""

    statement = select(PolicyConflict).where(
        PolicyConflict.left_rule_id == left_rule.id,
        PolicyConflict.right_rule_id == right_rule.id,
    )

    if db.scalars(statement).first() is not None:
        return

    comparison = compare_policy_rules(left_rule, right_rule)
    persist_policy_comparison(db, comparison)


def main() -> None:
    """Persist FAQ, campaign-exception and high-risk acceptance cases."""

    db = SessionLocal()

    try:
        official_version = load_version(
            db,
            "REFUND-POLICY",
            version_number=3,
        )
        faq_version = load_version(
            db,
            "REFUND-FAQ-001",
        )
        campaign_version = load_version(
            db,
            "DOUBLE-11-REFUND-NOTICE-2025",
        )
        invalid_version = load_version(
            db,
            "INVALID-UNLIMITED-REFUND-NOTICE",
        )

        official_statement = select(PolicyRule).where(
            PolicyRule.document_version_id == official_version.id,
            PolicyRule.rule_key == "refund.window_days",
            PolicyRule.conditions["membership_tier"].as_string()
            == "gold",
        )
        official_rule = db.scalars(official_statement).one()

        faq_rule = find_or_create_rule(
            db,
            faq_version,
            value=30,
            conditions={"membership_tier": "gold"},
            source_quote="FAQ：金卡会员享有 30 天无理由退款权益。",
        )
        campaign_rule = find_or_create_rule(
            db,
            campaign_version,
            value=30,
            conditions={
                "membership_tier": "gold",
                "campaign": "double_11",
            },
            source_quote="符合双十一活动条件的订单可在签收后 30 个自然日内申请退款。",
        )
        invalid_rule = find_or_create_rule(
            db,
            invalid_version,
            value="unlimited",
            conditions={},
            source_quote="所有商品均可在任何时间申请退款。",
        )

        persist_comparison_once(db, official_rule, faq_rule)
        persist_comparison_once(db, official_rule, campaign_rule)
        persist_comparison_once(db, official_rule, invalid_rule)

        db.commit()
        print("day10_acceptance_cases_persisted=3")

    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
