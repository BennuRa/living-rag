"""LangGraph definition for the Living RAG question-answering workflow."""

from __future__ import annotations

from functools import partial

from langgraph.graph import END, START, StateGraph
from sqlalchemy.orm import Session

from app.services.embedding import EmbeddingProvider
from app.services.llm import LLMProvider
from app.services.qa_nodes import (
    build_context_node,
    check_conflicts_node,
    classify_intent,
    generate_answer_node,
    grade_documents_node,
    load_context_node,
    retrieve_documents_node,
    safe_conflict_response_node,
    validate_citations_node,
)
from app.services.qa_state import LivingRAGState


def build_qa_graph(
    llm_provider: LLMProvider,
    db: Session,
    embedding_provider: EmbeddingProvider,
):
    """Build and compile the grounded question-answering graph."""

    retrieval_node = partial(
        retrieve_documents_node,
        db=db,
        embedding_provider=embedding_provider,
    )

    answer_node = partial(
        generate_answer_node,
        provider=llm_provider,
    )

    conflict_node = partial(
        check_conflicts_node,
        db=db,
    )

    graph_builder = StateGraph(LivingRAGState)

    graph_builder.add_node(
        "load_context",
        load_context_node,
    )

    graph_builder.add_node(
        "classify_intent",
        classify_intent,
    )

    graph_builder.add_node(
        "retrieve_documents",
        retrieval_node,
    )

    graph_builder.add_node(
        "grade_documents",
        grade_documents_node,
    )

    graph_builder.add_node(
        "check_conflicts",
        conflict_node,
    )

    graph_builder.add_node(
        "build_context",
        build_context_node,
    )

    graph_builder.add_node(
        "generate_answer",
        answer_node,
    )

    graph_builder.add_node(
        "safe_conflict_response",
        safe_conflict_response_node,
    )

    graph_builder.add_node(
        "validate_citations",
        validate_citations_node,
    )

    graph_builder.add_edge(
        START,
        "load_context",
    )

    graph_builder.add_edge(
        "load_context",
        "classify_intent",
    )

    graph_builder.add_edge(
        "classify_intent",
        "retrieve_documents",
    )

    graph_builder.add_edge(
        "retrieve_documents",
        "grade_documents",
    )

    graph_builder.add_edge(
        "grade_documents",
        "check_conflicts",
    )

    graph_builder.add_conditional_edges(
        "check_conflicts",
        lambda state: (
            "safe_conflict_response"
            if state.get("conflict_blocking", False)
            else "build_context"
        ),
        {
            "safe_conflict_response": "safe_conflict_response",
            "build_context": "build_context",
        },
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
        "safe_conflict_response",
        "validate_citations",
    )

    graph_builder.add_edge(
        "validate_citations",
        END,
    )

    return graph_builder.compile()