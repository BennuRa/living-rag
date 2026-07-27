"""HTTP routes for the Living RAG question-answering workflow."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.qa import (
    QuestionAnswerRequest,
    QuestionAnswerResponse,
)
from app.schemas.retrieval import RetrievalResult
from app.services.embedding_factory import create_embedding_provider
from app.services.llm import MockLLMProvider
from app.services.qa_graph import build_qa_graph
from app.services.retrieval import search_similar_chunks


router = APIRouter(
    prefix="/api/qa",
    tags=["question-answering"],
)


@router.post(
    "/answer",
    response_model=QuestionAnswerResponse,
)
def answer_question(
    request: QuestionAnswerRequest,
    db: Session = Depends(get_db),
) -> QuestionAnswerResponse:
    """Answer a question using retrieved evidence and citation validation."""
    embedding_provider = create_embedding_provider()

    query_embedding = embedding_provider.embed_texts(
        [request.question],
    )[0]

    rows = search_similar_chunks(
        db,
        query_embedding,
        limit=request.limit,
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
            similarity=1.0 - distance,
        )
        for chunk, document_version, document, distance in rows
    ]

    graph = build_qa_graph(
        provider=MockLLMProvider(),
    )

    result = graph.invoke(
        {
            "question": request.question,
            "retrieval_results": retrieval_results,
        },
    )

    return QuestionAnswerResponse(
        answer=result.get(
            "answer",
            "I do not have enough grounded evidence to answer this question.",
        ),
        citation_valid=result.get(
            "citation_valid",
            False,
        ),
        citations=result.get(
            "citations",
            [],
        ),
    )