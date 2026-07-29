"""LLM provider abstractions for the Living RAG workflow."""

from __future__ import annotations

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
                answer=(
                    "I do not have enough grounded evidence "
                    "to answer this question."
                ),
                conditions=[],
                citation_indices=[],
                confidence=0.0,
                limitations=[
                    "The knowledge base does not contain enough "
                    "relevant evidence for this question."
                ],
            )

        return GroundedAnswerDraft(
            answer=(
                "Based on the retrieved evidence [1], "
                "the answer is supported by the first source."
            ),
            conditions=[
                "The answer is limited to the retrieved knowledge-base evidence."
            ],
            citation_indices=[1],
            confidence=0.85,
            limitations=[],
        )