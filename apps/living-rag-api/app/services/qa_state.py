"""State definitions for the Living RAG question-answering workflow."""

from __future__ import annotations

from typing import TypedDict

from app.schemas.citation import Citation
from app.schemas.retrieval import RetrievalResult


class QAState(TypedDict, total=False):
    """Shared state passed between question-answering graph nodes."""

    question: str
    retrieval_results: list[RetrievalResult]
    context: str
    answer: str
    citations: list[Citation]
    citation_valid: bool
    error: str | None