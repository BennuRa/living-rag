"""LangGraph node functions for the Living RAG workflow."""

from app.services.citation_validation import (
    build_citations_from_answer,
    validate_answer_citations,
)
from app.services.llm import LLMProvider
from app.services.qa_context import build_retrieval_context
from app.services.qa_state import QAState


def build_context_node(
    state: QAState,
) -> dict[str, str]:
    """Build the LLM context from the retrieved evidence."""
    context = build_retrieval_context(
        state.get("retrieval_results", []),
    )

    return {
        "context": context,
    }


def generate_answer_node(
    state: QAState,
    provider: LLMProvider,
) -> dict[str, str]:
    """Generate an answer from the question and grounded context."""
    answer = provider.generate_answer(
        question=state.get("question", ""),
        context=state.get("context", ""),
    )

    return {
        "answer": answer,
    }


def validate_citations_node(
    state: QAState,
) -> dict[str, object]:
    """Validate answer citations and build citation objects."""
    answer = state.get("answer", "")
    results = state.get("retrieval_results", [])

    citation_valid = validate_answer_citations(
        answer,
        results,
    )

    if citation_valid:
        citations = build_citations_from_answer(
            answer,
            results,
        )
    else:
        citations = []

    return {
        "citation_valid": citation_valid,
        "citations": citations,
    }