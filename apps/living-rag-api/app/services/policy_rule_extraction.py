"""Deterministic extraction of structured policy rules."""

import re

from app.models.document import DocumentVersion
from app.schemas.policy_rule import (
    PolicyRuleExtraction,
    PolicyRuleKey,
)


MEMBERSHIP_WINDOW_PATTERN = re.compile(
    r"\|\s*(standard|silver|gold|platinum)\s*\|\s*(\d+)",
    re.IGNORECASE,
)


MEMBERSHIP_WINDOW_PROSE_PATTERN = re.compile(
    r"standard.*?silver.*?gold.*?platinum.*?\u5747\u9002\u7528\s*(\d+)\s*\u4e2a\u81ea\u7136\u65e5",
    re.IGNORECASE | re.DOTALL,
)


MEMBERSHIP_TIERS = (
    "standard",
    "silver",
    "gold",
    "platinum",
)


def _build_window_rule(
    document_version: DocumentVersion,
    *,
    membership_tier: str,
    window_days: int,
    source_quote: str,
) -> PolicyRuleExtraction:
    """Build one membership refund-window rule."""

    return PolicyRuleExtraction(
        rule_key=PolicyRuleKey.REFUND_WINDOW_DAYS,
        value=window_days,
        conditions={"membership_tier": membership_tier},
        source_quote=source_quote,
        document_version_id=document_version.id,
        effective_at=document_version.effective_at,
        expires_at=document_version.expires_at,
        confidence=0.95,
    )


def _extract_membership_window_rules(
    document_version: DocumentVersion,
) -> list[PolicyRuleExtraction]:
    """Extract membership windows from a table or prose."""

    content = document_version.content
    table_matches = list(
        MEMBERSHIP_WINDOW_PATTERN.finditer(content)
    )

    if table_matches:
        return [
            _build_window_rule(
                document_version,
                membership_tier=match.group(1).lower(),
                window_days=int(match.group(2)),
                source_quote=match.group(0).strip(),
            )
            for match in table_matches
        ]

    prose_match = MEMBERSHIP_WINDOW_PROSE_PATTERN.search(content)

    if prose_match is None:
        raise ValueError(
            "Refund membership window table was not found."
        )

    window_days = int(prose_match.group(1))
    source_quote = prose_match.group(0).strip()

    return [
        _build_window_rule(
            document_version,
            membership_tier=membership_tier,
            window_days=window_days,
            source_quote=source_quote,
        )
        for membership_tier in MEMBERSHIP_TIERS
    ]


def extract_policy_rules(
    document_version: DocumentVersion,
) -> list[PolicyRuleExtraction]:
    """Extract deterministic structured rules from one policy version."""

    rules = _extract_membership_window_rules(document_version)

    free_return_rule_added = False

    for line in document_version.content.splitlines():
        normalized_line = line.lower()

        if (
            not free_return_rule_added
            and "gold" in normalized_line
            and "platinum" in normalized_line
            and (
                "免费" in line
                or "平台承担" in line
                or "free" in normalized_line
                or "platform-paid" in normalized_line
                or "platform paid" in normalized_line
                or "return shipping" in normalized_line
            )
        ):
            rules.append(
                PolicyRuleExtraction(
                    rule_key=(
                        PolicyRuleKey.REFUND_MEMBER_FREE_RETURN_TIER
                    ),
                    value="gold",
                    conditions={"includes": "platinum"},
                    source_quote=line.strip(),
                    document_version_id=document_version.id,
                    effective_at=document_version.effective_at,
                    expires_at=document_version.expires_at,
                    confidence=0.95,
                )
            )
            free_return_rule_added = True

    return rules
