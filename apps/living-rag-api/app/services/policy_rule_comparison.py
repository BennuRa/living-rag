"""Deterministic comparison of structured policy rules."""

import json
from datetime import datetime

from app.models.policy_rule import PolicyRule
from app.schemas.policy_comparison import (
    PolicyComparisonSeverity,
    PolicyRuleComparison,
    PolicyRuleComparisonKind,
)


HIGH_RISK_TERMS = (
    "unlimited",
    "permanent",
    "forever",
    "无限期",
    "永久",
    "无时间限制",
)


def _effective_start(rule: PolicyRule) -> datetime:
    """Return a sortable effective start for a rule."""

    return rule.effective_at or datetime.min


def _rules_have_overlapping_period(
    left_rule: PolicyRule,
    right_rule: PolicyRule,
) -> bool:
    """Return whether two rule validity periods overlap."""

    if (
        left_rule.expires_at is not None
        and right_rule.effective_at is not None
        and left_rule.expires_at <= right_rule.effective_at
    ):
        return False

    if (
        right_rule.expires_at is not None
        and left_rule.effective_at is not None
        and right_rule.expires_at <= left_rule.effective_at
    ):
        return False

    return True


def _conditions_overlap(
    left_conditions: dict[str, object],
    right_conditions: dict[str, object],
) -> bool:
    """Return whether two condition sets can apply to the same case."""

    for key in left_conditions:
        if (
            key in right_conditions
            and left_conditions[key] != right_conditions[key]
        ):
            return False

    return True


def _is_strictly_more_specific(
    broad_conditions: dict[str, object],
    narrow_conditions: dict[str, object],
) -> bool:
    """Return whether narrow conditions strictly specialize broad ones."""

    if broad_conditions.keys() >= narrow_conditions.keys():
        return False

    for key, value in broad_conditions.items():
        if key not in narrow_conditions:
            return False
        if narrow_conditions[key] != value:
            return False

    return True


def _is_high_risk_rule(rule: PolicyRule) -> bool:
    """Return whether a rule contains an unlimited-refund risk signal."""

    normalized_source_quote = rule.source_quote.strip().lower()
    normalized_value = str(rule.value).strip().lower()

    return any(
        term in normalized_source_quote
        or term in normalized_value
        for term in HIGH_RISK_TERMS
    )


def _rule_match_key(rule: PolicyRule) -> tuple[str, str]:
    """Build a stable identity from semantic key and conditions."""

    conditions_json = json.dumps(
        rule.conditions,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return rule.rule_key, conditions_json


def _index_rules(
    rules: list[PolicyRule],
) -> dict[tuple[str, str], PolicyRule]:
    """Index rules and reject duplicate semantic identities."""

    indexed: dict[tuple[str, str], PolicyRule] = {}

    for rule in rules:
        match_key = _rule_match_key(rule)
        if match_key in indexed:
            raise ValueError(
                "Duplicate policy rules have the same "
                "rule key and conditions."
            )
        indexed[match_key] = rule

    return indexed


def _build_comparison(
    *,
    kind: PolicyRuleComparisonKind,
    severity: PolicyComparisonSeverity,
    left_rule: PolicyRule | None,
    right_rule: PolicyRule | None,
    left_document_version_id,
    right_document_version_id,
    reason: str,
    recommended_action: str,
    evidence: list[str],
) -> PolicyRuleComparison:
    """Build a validated comparison result."""

    rule = right_rule or left_rule
    assert rule is not None

    return PolicyRuleComparison(
        kind=kind,
        severity=severity,
        rule_key=rule.rule_key,
        left_rule_id=left_rule.id if left_rule else None,
        right_rule_id=right_rule.id if right_rule else None,
        left_document_version_id=left_document_version_id,
        right_document_version_id=right_document_version_id,
        reason=reason,
        recommended_action=recommended_action,
        evidence=evidence,
    )


def compare_policy_rules(
    left_rule: PolicyRule,
    right_rule: PolicyRule,
) -> PolicyRuleComparison:
    """Compare two rules with the same semantic rule key."""

    if left_rule.rule_key != right_rule.rule_key:
        raise ValueError(
            "Cannot compare rules with different rule keys."
        )

    evidence = [
        left_rule.source_quote,
        right_rule.source_quote,
    ]

    if _is_high_risk_rule(left_rule) or _is_high_risk_rule(right_rule):
        return _build_comparison(
            kind=PolicyRuleComparisonKind.HIGH_RISK_ERROR,
            severity=PolicyComparisonSeverity.HIGH,
            left_rule=left_rule,
            right_rule=right_rule,
            left_document_version_id=left_rule.document_version_id,
            right_document_version_id=right_rule.document_version_id,
            reason="规则包含无限期或永久退款风险信号。",
            recommended_action="立即暂停自动采用，标记文档无效并创建人工审核任务。",
            evidence=evidence,
        )

    if not _rules_have_overlapping_period(
        left_rule,
        right_rule,
    ):
        return _build_comparison(
            kind=PolicyRuleComparisonKind.HISTORICAL_DIFFERENCE,
            severity=PolicyComparisonSeverity.LOW,
            left_rule=left_rule,
            right_rule=right_rule,
            left_document_version_id=left_rule.document_version_id,
            right_document_version_id=right_rule.document_version_id,
            reason="两条规则的有效期不重叠，属于历史版本差异。",
            recommended_action="保留两条历史规则，不创建冲突审核任务。",
            evidence=evidence,
        )

    if not _conditions_overlap(
        left_rule.conditions,
        right_rule.conditions,
    ):
        return _build_comparison(
            kind=PolicyRuleComparisonKind.UPDATE,
            severity=PolicyComparisonSeverity.LOW,
            left_rule=left_rule,
            right_rule=right_rule,
            left_document_version_id=left_rule.document_version_id,
            right_document_version_id=right_rule.document_version_id,
            reason="两条规则的条件互斥，属于不同适用场景。",
            recommended_action="保留两条规则，并按条件分别匹配。",
            evidence=evidence,
        )

    if left_rule.value == right_rule.value:
        return _build_comparison(
            kind=PolicyRuleComparisonKind.UPDATE,
            severity=PolicyComparisonSeverity.LOW,
            left_rule=left_rule,
            right_rule=right_rule,
            left_document_version_id=left_rule.document_version_id,
            right_document_version_id=right_rule.document_version_id,
            reason="两条规则的适用条件和值相同。",
            recommended_action="保留最新版本，并保留历史证据。",
            evidence=evidence,
        )

    if _is_strictly_more_specific(
        left_rule.conditions,
        right_rule.conditions,
    ) or _is_strictly_more_specific(
        right_rule.conditions,
        left_rule.conditions,
    ):
        return _build_comparison(
            kind=PolicyRuleComparisonKind.CONDITIONAL_EXCEPTION,
            severity=PolicyComparisonSeverity.MEDIUM,
            left_rule=left_rule,
            right_rule=right_rule,
            left_document_version_id=left_rule.document_version_id,
            right_document_version_id=right_rule.document_version_id,
            reason="更具体的条件规则只适用于特定场景，属于条件性例外。",
            recommended_action="保留通用规则和例外规则，优先匹配更具体条件。",
            evidence=evidence,
        )

    return _build_comparison(
        kind=PolicyRuleComparisonKind.CONFLICT,
        severity=PolicyComparisonSeverity.HIGH,
        left_rule=left_rule,
        right_rule=right_rule,
        left_document_version_id=left_rule.document_version_id,
        right_document_version_id=right_rule.document_version_id,
        reason="两条规则在相同有效期和适用条件下给出了不同结论，存在冲突。",
        recommended_action="暂停自动裁定，保留双方证据并创建人工审核任务。",
        evidence=evidence,
    )


def compare_policy_rule_sets(
    *,
    left_rules: list[PolicyRule],
    right_rules: list[PolicyRule],
    left_document_version_id,
    right_document_version_id,
) -> list[PolicyRuleComparison]:
    """Compare two versions of a rule set."""

    left_index = _index_rules(left_rules)
    right_index = _index_rules(right_rules)
    comparisons: list[PolicyRuleComparison] = []

    for match_key, left_rule in left_index.items():
        if match_key not in right_index:
            raise NotImplementedError(
                "Removed policy rules are not implemented yet."
            )

        comparisons.append(
            compare_policy_rules(
                left_rule,
                right_index[match_key],
            )
        )

    for match_key, right_rule in right_index.items():
        if match_key in left_index:
            continue

        if _is_high_risk_rule(right_rule):
            comparisons.append(
                _build_comparison(
                    kind=PolicyRuleComparisonKind.HIGH_RISK_ERROR,
                    severity=PolicyComparisonSeverity.HIGH,
                    left_rule=None,
                    right_rule=right_rule,
                    left_document_version_id=left_document_version_id,
                    right_document_version_id=right_document_version_id,
                    reason="新增规则包含无限期或永久退款风险信号。",
                    recommended_action="立即暂停采用，标记文档无效并创建人工审核任务。",
                    evidence=[right_rule.source_quote],
                )
            )
        else:
            comparisons.append(
                _build_comparison(
                    kind=PolicyRuleComparisonKind.UPDATE,
                    severity=PolicyComparisonSeverity.LOW,
                    left_rule=None,
                    right_rule=right_rule,
                    left_document_version_id=left_document_version_id,
                    right_document_version_id=right_document_version_id,
                    reason="新版本新增了一条结构化政策规则。",
                    recommended_action="记录为版本更新，并在审核后采用新规则。",
                    evidence=[right_rule.source_quote],
                )
            )

    comparisons.sort(
        key=lambda comparison: (
            comparison.rule_key.value,
            comparison.kind.value,
        )
    )
    return comparisons
