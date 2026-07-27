"""Citation validation for the Living RAG workflow."""

import re

from app.schemas.citation import Citation
from app.schemas.retrieval import RetrievalResult


_CITATION_PATTERN = re.compile(r"\[(\d+)\]")


def validate_answer_citations(
    answer: str,
    results: list[RetrievalResult],
) -> bool:
    """Return whether every citation marker points to a retrieved result."""
    if not answer.strip():
        return False

    citation_numbers = [
        int(match)
        for match in _CITATION_PATTERN.findall(answer)
    ]

    if not citation_numbers:
        return False

    result_count = len(results)

    return all(
        1 <= citation_number <= result_count
        for citation_number in citation_numbers
    )


def build_citations_from_answer(
    answer: str,
    results: list[RetrievalResult],
) -> list[Citation]:
    """Build unique citations from valid answer citation markers."""
    if not validate_answer_citations(answer, results):
        return []

    citation_numbers = [
        int(match)
        for match in _CITATION_PATTERN.findall(answer)
    ]

    citations: list[Citation] = []
    seen_numbers: set[int] = set()

    for citation_number in citation_numbers:
        if citation_number in seen_numbers:
            continue

        seen_numbers.add(citation_number)
        result = results[citation_number - 1]

        citations.append(
            Citation(
                document_id=result.document_id,
                document_version_id=result.document_version_id,
                chunk_id=result.chunk_id,
                quote=result.content,
                relevance_score=result.similarity,
            ),
        )

    return citations