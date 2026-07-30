"""LLM provider abstractions for the Living RAG workflow."""

from __future__ import annotations

import re
from abc import ABC, abstractmethod

from app.schemas.qa import GroundedAnswerDraft


class LLMProvider(ABC):
    """Abstract interface for answer-generating language model providers."""

    @abstractmethod
    def generate_answer(
        self,
        question: str,
        context: str,
    ) -> GroundedAnswerDraft:
        """Generate a structured answer grounded in retrieved evidence."""
        raise NotImplementedError


class MockLLMProvider(LLMProvider):
    """Deterministic LLM provider for local development and tests."""

    def generate_answer(
        self,
        question: str,
        context: str,
    ) -> GroundedAnswerDraft:
        """Generate a deterministic structured answer for testing."""

        if not question.strip():
            raise ValueError("Question must not be blank.")

        if not context.strip():
            return GroundedAnswerDraft(
                answer="当前知识库中没有足够的有效证据，暂时无法可靠回答这个问题。",
                conditions=[],
                citation_indices=[],
                confidence=0.0,
                limitations=[
                    "当前检索结果没有提供足够的相关知识库证据。",
                ],
            )

        normalized_question = question.strip().lower()
        context_lower = context.lower()

        if any(
            keyword in normalized_question
            for keyword in ("退款", "退货", "签收后多久", "退款时限")
        ):
            tier_windows = (
                ("standard", "普通会员", 7),
                ("silver", "银卡会员", 10),
                ("gold", "金卡会员", 15),
                ("platinum", "铂金会员", 20),
            )

            matched_tier = next(
                (
                    (display_name, days)
                    for policy_tier, display_name, days in tier_windows
                    if policy_tier in context_lower
                    and (
                        policy_tier in normalized_question
                        or display_name in question
                        or (policy_tier == "standard" and "普通" in question)
                    )
                ),
                None,
            )

            if matched_tier is not None:
                tier_name, window_days = matched_tier

                return GroundedAnswerDraft(
                    answer=(
                        f"目前{tier_name}在订单签收后的 "
                        f"{window_days} 天内可以申请退款。"
                        "退款期限从订单签收日期开始计算。[1]"
                    ),
                    conditions=[
                        "退款申请期限从订单签收日期开始计算。",
                        "如果存在活动规则或特殊商品条件，应以对应有效政策和人工审核结果为准。",
                    ],
                    citation_indices=[1],
                    confidence=0.9,
                    limitations=[],
                )

            window_match = re.search(
                r"(?:within|在|签收后)\s*(\d+)\s*(?:days|天)",
                context_lower,
            )

            if window_match is not None:
                window_days = window_match.group(1)

                return GroundedAnswerDraft(
                    answer=(
                        f"根据当前检索到的政策，相关退款期限为签收后的 "
                        f"{window_days} 天内。[1]"
                    ),
                    conditions=[
                        "退款期限从订单签收日期开始计算。",
                    ],
                    citation_indices=[1],
                    confidence=0.85,
                    limitations=[],
                )

        return GroundedAnswerDraft(
            answer=(
                "根据当前检索到的知识库证据，"
                "相关结论可以由第一个有效来源支持。[1]"
            ),
            conditions=[
                "回答仅基于当前检索到的知识库证据。",
            ],
            citation_indices=[1],
            confidence=0.85,
            limitations=[],
        )