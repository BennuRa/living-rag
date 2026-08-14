from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas.citation import Citation


def test_citation_accepts_a_valid_evidence_reference() -> None:
    citation = Citation(
        document_id=uuid4(),
        document_version_id=uuid4(),
        chunk_id=uuid4(),
        document_title="退款政策",
        version_number=3,
        source_type="official_policy",
        governance_status="active",
        quote="普通会员在签收后 15 天内可申请退款。",
        relevance_score=0.92,
    )

    assert citation.version_number == 3
    assert citation.governance_status == "active"
    assert citation.relevance_score == 0.92


@pytest.mark.parametrize(
    ("kwargs", "field_name"),
    [
        ({"quote": ""}, "quote"),
        ({"version_number": 0}, "version_number"),
        ({"relevance_score": -0.01}, "relevance_score"),
        ({"relevance_score": 1.01}, "relevance_score"),
        ({"unknown_field": "unexpected"}, "unknown_field"),
    ],
)
def test_citation_rejects_invalid_evidence(
    kwargs: dict[str, object],
    field_name: str,
) -> None:
    valid_fields = {
        "document_id": uuid4(),
        "document_version_id": uuid4(),
        "chunk_id": uuid4(),
        "quote": "可核验的原文证据。",
    }

    with pytest.raises(ValidationError) as exc_info:
        Citation(**{**valid_fields, **kwargs})

    assert exc_info.value.errors()[0]["loc"] == (field_name,)