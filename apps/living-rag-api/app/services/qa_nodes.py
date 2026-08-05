"""LangGraph node functions for the Living RAG workflow."""

from datetime import UTC, datetime

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.document import DocumentGovernanceStatus
from app.models.policy_conflict import PolicyConflict, PolicyConflictStatus
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


def load_context_node(
    state: LivingRAGState,
) -> dict[str, object]:
    """Normalize the initial request context before the QA workflow starts."""

    question = state.get("question", "").strip()

    if not question:
        raise ValueError("Question must not be blank.")

    limit = state.get("limit", 5)

    if not isinstance(limit, int) or isinstance(limit, bool):
        raise ValueError("limit must be an integer.")

    if limit <= 0:
        raise ValueError("limit must be greater than zero.")

    normalized_state: dict[str, object] = {
        "question": question,
        "limit": limit,
    }

    user_id = state.get("user_id")

    if user_id is not None:
        normalized_state["user_id"] = user_id.strip()

    trace_id = state.get("trace_id")

    if trace_id is not None:
        normalized_state["trace_id"] = trace_id.strip()

    return normalized_state


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
        query_text=question,
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

    intent = state.get("intent")

    if intent == "unknown":
        return {
            "graded_results": [],
        }

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


def safe_conflict_response_node(
    state: LivingRAGState,
) -> dict[str, object]:
    """Return a conservative answer when an open conflict blocks a conclusion."""

    graded_results = state.get("graded_results", [])
    conflict_notice = state.get("conflict_notice", "")
    conflict_summaries = state.get("conflict_summaries", [])

    answer = conflict_notice or (
        "当前政策证据存在尚未解决的冲突，"
        "暂时无法给出单一确定结论。"
    )

    if conflict_summaries:
        answer = (
            f"{answer} "
            f"冲突摘要：{'：'.join(conflict_summaries)}"
        )

    # 安全回答仍然要经过原有 citation validation 节点。
    # 因此这里把当前 graded_results 的编号全部交给引用校验。
    citation_indices = list(
        range(1, len(graded_results) + 1)
    )

    if citation_indices:
        answer = (
            f"{answer} "
            f"{' '.join(f'[{index}]' for index in citation_indices)}"
        )

    return {
        "answer": answer,
        "conditions": [
            "最终政策结论需要人工审核确认。",
        ],
        "citation_indices": citation_indices,
        "confidence": 0.0,
        "limitations": [
            "存在未决政策冲突，系统未对冲突来源进行单方面裁定。",
        ],
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


def check_conflicts_node(
    state: LivingRAGState,
    db: Session,
) -> dict[str, object]:
    """Find open conflicts that affect the evidence used for this question."""

    graded_results = state.get("graded_results", [])

    # 没有经过筛选的有效证据时，不把“没有证据”误判成“存在冲突”。
    if not graded_results:
        return {
            "conflict_summaries": [],
            "conflict_blocking": False,
            "conflict_notice": "",
        }

    # 当前问答真正使用的是 graded_results 中的文档版本。
    version_ids = {
        result.document_version_id
        for result in graded_results
    }

    # 只查询：
    # 1. 与当前证据版本有关的冲突；
    # 2. 仍然处于 open 状态的冲突。
    statement = select(PolicyConflict).where(
        PolicyConflict.status == PolicyConflictStatus.OPEN.value,
        or_(
            PolicyConflict.left_document_version_id.in_(version_ids),
            PolicyConflict.right_document_version_id.in_(version_ids),
        ),
    )

    conflicts = list(db.scalars(statement).all())

    # Day 12 的阻断规则：
    # - conflict：真正的规则冲突，需要阻断；
    # - high_risk_error：高风险错误，需要阻断；
    # - historical_difference：历史差异，不阻断；
    # - update：正常版本更新，不阻断；
    # - conditional_exception：条件性例外，不在这里直接阻断。
    relevant_conflicts = [
        conflict
        for conflict in conflicts
        if conflict.kind in {
            "conflict",
            "high_risk_error",
        }
    ]

    if not relevant_conflicts:
        return {
            "conflict_summaries": [],
            "conflict_blocking": False,
            "conflict_notice": "",
        }

    # 当前 State 中 conflict_summaries 的类型是 list[str]，
    # 所以这里先把数据库冲突转换为可读摘要。
    summaries = [
        (
            f"{conflict.kind} "
            f"({conflict.severity}) "
            f"for {conflict.rule_key}: "
            f"{conflict.reason}"
        )
        for conflict in relevant_conflicts
    ]

    notice = (
        "当前检索到的有效证据之间存在尚未完成人工审核的政策冲突。"
        "系统不会在冲突未决时擅自选择单一政策结论。"
        "相关来源和证据已保留，建议提交人工审核。"
    )

    return {
        "conflict_summaries": summaries,
        "conflict_blocking": True,
        "conflict_notice": notice,
    }
