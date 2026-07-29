"""LangGraph definition for the Living RAG question-answering workflow."""

from __future__ import annotations

from functools import partial

from langgraph.graph import END, START, StateGraph
from sqlalchemy.orm import Session

from app.services.embedding import EmbeddingProvider
from app.services.llm import LLMProvider
from app.services.qa_nodes import (
    build_context_node,
    classify_intent,
    generate_answer_node,
    grade_documents_node,
    retrieve_documents_node,
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

    graph_builder = StateGraph(LivingRAGState)

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