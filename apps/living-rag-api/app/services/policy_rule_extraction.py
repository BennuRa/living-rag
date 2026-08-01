import re

from app.models.document import DocumentVersion
from app.schemas.policy_rule import (
    PolicyRuleExtraction,
    PolicyRuleKey,
)


MEMBERSHIP_WINDOW_PATTERN = re.compile(
    r"\| *(standard|silver|gold|platinum) *\| *(\d+)",
    re.IGNORECASE,
)


def extract_policy_rules(
    document_version: DocumentVersion,
) -> list[PolicyRuleExtraction]:
    """Extract deterministic structured rules from one policy version."""

    content = document_version.content
    rules: list[PolicyRuleExtraction] = []

    matches = list(
        MEMBERSHIP_WINDOW_PATTERN.finditer(content)
    )

    if not matches:
        raise ValueError(
            "Refund membership window table was not found."
        )

    for match in matches:
        membership_tier = match.group(1).lower()
        window_days = int(match.group(2))
        source_quote = match.group(0).strip()

        rule = PolicyRuleExtraction(
            rule_key=PolicyRuleKey.REFUND_WINDOW_DAYS,
            value=window_days,
            conditions={
                "membership_tier": membership_tier,
            },
            source_quote=source_quote,
            document_version_id=document_version.id,
            effective_at=document_version.effective_at,
            expires_at=document_version.expires_at,
            confidence=0.95,
        )
        rules.append(rule)

    free_return_rule_added = False

    for line in content.splitlines():
        normalized_line = line.lower()

        if (
            not free_return_rule_added
            and "gold" in normalized_line
            and "platinum" in normalized_line
        ):
            rule = PolicyRuleExtraction(
                rule_key=PolicyRuleKey.REFUND_MEMBER_FREE_RETURN_TIER,
                value="gold",
                conditions={
                    "includes": "platinum",
                },
                source_quote=line.strip(),
                document_version_id=document_version.id,
                effective_at=document_version.effective_at,
                expires_at=document_version.expires_at,
                confidence=0.95,
            )
            rules.append(rule)
            free_return_rule_added = True

    return rules