"""State definitions for the Living RAG question-answering graph."""

from typing import Literal, TypedDict

from app.schemas.qa import Citation
from app.schemas.retrieval import RetrievalResult


Intent = Literal[
    "policy_qa",
    "order_membership",
    "refund_request",
    "high_risk_operation",
    "unknown",
]


class LivingRAGState(TypedDict, total=False):
    """Shared state passed between LangGraph nodes during one QA run."""

    question: str
    user_id: str
    trace_id: str
    limit: int

    intent: Intent

    retrieval_results: list[RetrievalResult]
    graded_results: list[RetrievalResult]
    context: str

    answer: str
    conditions: list[str]
    citation_indices: list[int]
    citations: list[Citation]
    confidence: float
    limitations: list[str]

    citation_valid: bool
    error: str | None

    conflict_summaries: list[str]
    conflict_blocking: bool
    conflict_notice: str


QAState = LivingRAGState