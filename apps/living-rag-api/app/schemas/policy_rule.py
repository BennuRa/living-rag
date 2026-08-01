"""Pydantic schemas for structured policy rules."""

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class PolicyRuleKey(StrEnum):
    """Supported structured policy rule keys for Day 9."""

    REFUND_WINDOW_DAYS = "refund.window_days"
    REFUND_RETURN_SHIPPING_PAYER = "refund.return_shipping_payer"
    REFUND_MEMBER_FREE_RETURN_TIER = "refund.member_free_return_tier"
    REFUND_EXCLUDED_CATEGORIES = "refund.excluded_categories"
    DELIVERY_DELAY_COMPENSATION = "delivery.delay_compensation"
    EXCHANGE_WINDOW_DAYS = "exchange.window_days"
    MEMBERSHIP_BENEFIT = "membership.benefit"


class PolicyRuleExtraction(BaseModel):
    """One validated structured rule extracted from a document version."""

    model_config = ConfigDict(extra="forbid")

    rule_key: PolicyRuleKey
    value: int | float | str | bool | list[str]
    conditions: dict[str, str] = Field(default_factory=dict)
    source_quote: str = Field(min_length=1)
    document_version_id: UUID
    effective_at: datetime | None = None
    expires_at: datetime | None = None
    confidence: float = Field(ge=0.0, le=1.0)