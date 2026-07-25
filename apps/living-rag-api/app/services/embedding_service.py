from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.document_chunk import DocumentChunk
from app.services.embedding import EmbeddingProvider


def embed_pending_chunks(
    db: Session,
    provider: EmbeddingProvider,
    batch_size: int = 100,
) -> int:
    """为尚未生成 embedding 的文档 Chunk 批量生成并写入向量。"""

    if batch_size <= 0:
        raise ValueError("batch_size must be greater than zero.")

    processed_count = 0

    while True:
        statement = (
            select(DocumentChunk)
            .where(DocumentChunk.embedding.is_(None))
            .order_by(DocumentChunk.id)
            .limit(batch_size)
        )

        chunks = db.scalars(statement).all()

        if not chunks:
            break

        contents = [
            chunk.content
            for chunk in chunks
        ]

        embeddings = provider.embed_texts(contents)

        if len(embeddings) != len(chunks):
            raise ValueError(
                "Embedding provider returned a different number of vectors "
                "than the input chunks.",
            )

        for chunk, embedding in zip(
            chunks,
            embeddings,
            strict=True,
        ):
            chunk.embedding = embedding

        db.flush()
        processed_count += len(chunks)

    return processed_count