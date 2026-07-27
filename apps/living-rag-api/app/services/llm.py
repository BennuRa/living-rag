"""LLM provider abstractions for the Living RAG workflow."""

from __future__ import annotations

from abc import ABC, abstractmethod


class LLMProvider(ABC):
    """Abstract interface for answer-generating language model providers."""

    @abstractmethod
    def generate_answer(
        self,
        question: str,
        context: str,
    ) -> str:
        """Generate an answer grounded in the supplied retrieval context."""
        raise NotImplementedError


class MockLLMProvider(LLMProvider):
    """Deterministic LLM provider for local development and tests."""

    def generate_answer(
        self,
        question: str,
        context: str,
    ) -> str:
        """Generate a deterministic grounded answer for testing."""
        if not question.strip():
            raise ValueError("Question must not be blank.")

        if not context.strip():
            return (
                "I do not have enough grounded evidence "
                "to answer this question."
            )

        return (
            "Based on the retrieved evidence [1], "
            "the answer is supported by the first source."
        )