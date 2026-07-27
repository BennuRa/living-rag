"""LangGraph definition for the Living RAG question-answering workflow."""

from __future__ import annotations

from functools import partial

from langgraph.graph import END, START, StateGraph

from app.services.llm import LLMProvider
from app.services.qa_nodes import (
    build_context_node,
    generate_answer_node,
    validate_citations_node,
)
from app.services.qa_state import QAState


def build_qa_graph(provider: LLMProvider):
    """Build and compile the grounded question-answering graph."""
    answer_node = partial(
        generate_answer_node,
        provider=provider,
    )

    graph_builder = StateGraph(QAState)

    graph_builder.add_node(
        "build_context",
        build_context_node,
    )
    graph_builder.add_node(
        "generate_answer",
        answer_node,
    )
    graph_builder.add_node(
        "validate_citations",
        validate_citations_node,
    )

    graph_builder.add_edge(
        START,
        "build_context",
    )
    graph_builder.add_edge(
        "build_context",
        "generate_answer",
    )
    graph_builder.add_edge(
        "generate_answer",
        "validate_citations",
    )
    graph_builder.add_edge(
        "validate_citations",
        END,
    )

    return graph_builder.compile()