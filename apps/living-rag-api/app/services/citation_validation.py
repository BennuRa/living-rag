"""Citation validation for the Living RAG workflow."""

import re
from datetime import UTC, datetime

from app.models.document import DocumentGovernanceStatus
from app.schemas.citation import Citation
from app.schemas.retrieval import RetrievalResult


_CITATION_PATTERN = re.compile(r"\[(\d+)\]")


def validate_answer_citations(
    answer: str,
    results: list[RetrievalResult],
    citation_indices: list[int] | None = None,
) -> bool:
    """Validate citation references and the evidence behind them."""

    if not answer.strip():
        return False

    textual_citation_numbers = [
        int(match)
        for match in _CITATION_PATTERN.findall(answer)
    ]

    if citation_indices is None:
        citation_numbers = textual_citation_numbers
    else:
        citation_numbers = citation_indices

        if set(textual_citation_numbers) != set(citation_indices):
            return False

    if not citation_numbers:
        return False

    result_count = len(results)

    if not all(
        type(citation_number) is int
        and 1 <= citation_number <= result_count
        for citation_number in citation_numbers
    ):
        return False

    now = datetime.now(UTC)

    for citation_number in citation_numbers:
        result = results[citation_number - 1]

        if result.governance_status != DocumentGovernanceStatus.ACTIVE:
            return False

        if not result.content.strip():
            return False

        if result.effective_at is not None and result.effective_at > now:
            return False

        if result.expires_at is not None and result.expires_at <= now:
            return False

    return True

def build_citations_from_answer(
    answer: str,
    results: list[RetrievalResult],
    citation_indices: list[int] | None = None,
) -> list[Citation]:
    """Build unique citations from validated structured or textual references."""

    if not validate_answer_citations(
        answer,
        results,
        citation_indices,
    ):
        return []

    if citation_indices is None:
        citation_numbers = [
            int(match)
            for match in _CITATION_PATTERN.findall(answer)
        ]
    else:
        citation_numbers = citation_indices

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
                document_title=result.document_title,
                version_number=result.version_number,
                source_type=result.source_type,
                governance_status=result.governance_status,
                effective_at=result.effective_at,
                expires_at=result.expires_at,
                quote=result.content,
                relevance_score=result.similarity,
            ),
        )

    return citations