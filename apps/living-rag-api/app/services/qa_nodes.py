"""LangGraph node functions for the Living RAG workflow."""

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models.document import DocumentGovernanceStatus
from app.schemas.retrieval import RetrievalResult
from app.services.citation_validation import (
    build_citations_from_answer,
    validate_answer_citations,
)
from app.services.embedding import EmbeddingProvider
from app.services.llm import LLMProvider
from app.services.qa_context import build_retrieval_context
from app.services.qa_state import QAState, LivingRAGState
from app.services.retrieval import search_similar_chunks


def classify_intent(
    state: LivingRAGState,
) -> dict[str, str]:
    """Classify the user request using deterministic safety-first rules."""

    question = state.get("question", "").strip()

    if not question:
        raise ValueError("Question must not be blank.")

    normalized_question = question.lower()

    high_risk_keywords = (
        "删除政策",
        "删除退款政策",
        "删除退款规则",
        "删除文档",
        "删除知识库",
        "修改政策",
        "修改退款政策",
        "修改退款规则",
        "修改知识库规则",
        "直接退款",
        "强制退款",
        "delete policy",
        "delete document",
        "delete knowledge base",
        "modify policy",
        "modify refund policy",
        "modify refund rule",
        "issue refund directly",
        "force refund",
    )

    if any(keyword in normalized_question for keyword in high_risk_keywords):
        return {
            "intent": "high_risk_operation",
        }

    refund_request_keywords = (
        "我要申请退款",
        "申请退款",
        "提交退款",
        "发起退款",
        "我要退货退款",
        "请求退款",
        "request a refund",
        "apply for refund",
        "submit refund",
    )

    if any(keyword in normalized_question for keyword in refund_request_keywords):
        return {
            "intent": "refund_request",
        }

    order_membership_keywords = (
        "订单",
        "订单号",
        "会员",
        "会员等级",
        "能退款吗",
        "可以退款吗",
        "符合退款条件吗",
        "我能退款吗",
        "order",
        "membership",
        "member",
        "eligible for a refund",
    )

    if any(keyword in normalized_question for keyword in order_membership_keywords):
        return {
            "intent": "order_membership",
        }

    policy_keywords = (
        "政策",
        "规则",
        "时限",
        "期限",
        "多久",
        "运费",
        "退款条件",
        "退货条件",
        "退款标准",
        "policy",
        "rule",
        "window",
        "deadline",
        "shipping fee",
        "refund condition",
    )

    if any(keyword in normalized_question for keyword in policy_keywords):
        return {
            "intent": "policy_qa",
        }

    return {
        "intent": "unknown",
    }

def retrieve_documents_node(
    state: LivingRAGState,
    db: Session,
    embedding_provider: EmbeddingProvider,
) -> dict[str, list[RetrievalResult]]:
    """Retrieve current and relevant document chunks for the user question."""

    question = state.get("question", "").strip()

    if not question:
        raise ValueError("Question must not be blank.")

    limit = state.get("limit", 5)

    query_embedding = embedding_provider.embed_texts(
        [question],
    )[0]

    rows = search_similar_chunks(
        db,
        query_embedding,
        limit=limit,
        now=datetime.now(UTC),
    )

    retrieval_results = [
        RetrievalResult(
            document_id=document.id,
            document_version_id=document_version.id,
            chunk_id=chunk.id,
            document_title=document.title,
            version_number=document_version.version_number,
            source_type=document_version.source_type,
            governance_status=document_version.governance_status,
            effective_at=document_version.effective_at,
            expires_at=document_version.expires_at,
            content=chunk.content,
            similarity=1.0 - float(distance),
        )
        for chunk, document_version, document, distance in rows
    ]

    return {
        "retrieval_results": retrieval_results,
    }


def grade_documents_node(
    state: LivingRAGState,
) -> dict[str, list[RetrievalResult]]:
    """Keep only current, non-blank, sufficiently relevant evidence."""

    retrieval_results = state.get("retrieval_results", [])

    graded_results = [
        result
        for result in retrieval_results
        if (
            result.governance_status == DocumentGovernanceStatus.ACTIVE
            and result.content.strip()
            and result.similarity >= 0.2
        )
    ]

    return {
        "graded_results": graded_results,
    }


def build_context_node(
    state: LivingRAGState,
) -> dict[str, str]:
    """Build the LLM context from graded or retrieved evidence."""

    graded_results = state.get("graded_results")

    if graded_results is None:
        results = state.get("retrieval_results", [])
    else:
        results = graded_results

    context = build_retrieval_context(results)

    return {
        "context": context,
    }


def generate_answer_node(
    state: LivingRAGState,
    provider: LLMProvider,
) -> dict[str, object]:
    """Generate and store a structured grounded answer."""

    draft = provider.generate_answer(
        question=state.get("question", ""),
        context=state.get("context", ""),
    )

    return {
        "answer": draft.answer,
        "conditions": draft.conditions,
        "citation_indices": draft.citation_indices,
        "confidence": draft.confidence,
        "limitations": draft.limitations,
    }


def validate_citations_node(
    state: LivingRAGState,
) -> dict[str, object]:
    """Validate structured citations against the graded evidence."""

    answer = state.get("answer", "")
    citation_indices = state.get("citation_indices")
    graded_results = state.get("graded_results")

    if graded_results is None:
        results = state.get("retrieval_results", [])
    else:
        results = graded_results

    citation_valid = validate_answer_citations(
        answer,
        results,
        citation_indices,
    )

    if citation_valid:
        citations = build_citations_from_answer(
            answer,
            results,
            citation_indices,
        )
    else:
        citations = []

    return {
        "citation_valid": citation_valid,
        "citations": citations,
    }