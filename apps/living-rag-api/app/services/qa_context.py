"""Context formatting for the Living RAG question-answering workflow."""

from app.schemas.retrieval import RetrievalResult


def build_retrieval_context(
    results: list[RetrievalResult],
) -> str:
    """Format retrieval results into citation-friendly LLM context."""
    if not results:
        return ""

    sections: list[str] = []

    for index, result in enumerate(results, start=1):
        sections.append(
            "\n".join(
                [
                    f"[{index}]",
                    f"Document title: {result.document_title}",
                    f"Document version: v{result.version_number}",
                    f"Source type: {result.source_type.value}",
                    f"Governance status: {result.governance_status.value}",
                    f"Chunk ID: {result.chunk_id}",
                    f"Similarity: {result.similarity:.4f}",
                    "Content:",
                    result.content,
                ],
            ),
        )

    return "\n\n".join(sections)