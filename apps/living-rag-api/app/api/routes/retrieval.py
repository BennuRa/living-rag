"""HTTP routes for vector retrieval."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.retrieval import (
    RetrievalResult,
    RetrievalSearchRequest,
)
from app.services.embedding_factory import create_embedding_provider
from app.services.retrieval import search_similar_chunks


router = APIRouter(
    prefix="/api/retrieval",
    tags=["retrieval"],
)


@router.post(
    "/search",
    response_model=list[RetrievalResult],
)
def search_retrieval(
    request: RetrievalSearchRequest,
    db: Session = Depends(get_db),
) -> list[RetrievalResult]:
    """使用向量检索返回当前有效的相关文档 Chunk。"""
    provider = create_embedding_provider()

    query_embedding = provider.embed_texts(
        [request.query],
    )[0]

    rows = search_similar_chunks(
        db,
        query_embedding,
        query_text=request.query,
        limit=request.limit,
        as_of_date=request.as_of_date,
    )

    return [
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