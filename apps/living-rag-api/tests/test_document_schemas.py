from datetime import datetime

import pytest
from pydantic import ValidationError

from app.models.document import DocumentSourceType
from app.schemas.document import DocumentUploadForm


def test_document_upload_form_accepts_valid_data() -> None:
    form = DocumentUploadForm(
        title="会员退款政策",
        domain="refund",
        policy_key="REFUND-POLICY",
        source_type=DocumentSourceType.OFFICIAL_POLICY,
        version_number=1,
        effective_at=datetime.fromisoformat("2026-07-21T00:00:00+08:00"),
    )

    assert form.title == "会员退款政策"
    assert form.domain == "refund"
    assert form.policy_key == "REFUND-POLICY"
    assert form.source_type is DocumentSourceType.OFFICIAL_POLICY


def test_document_upload_form_rejects_naive_datetime() -> None:
    with pytest.raises(
        ValidationError,
        match="Datetime values must include a timezone offset.",
    ):
        DocumentUploadForm(
            title="会员退款政策",
            domain="refund",
            policy_key="REFUND-POLICY",
            source_type=DocumentSourceType.OFFICIAL_POLICY,
            version_number=1,
            effective_at="2026-07-21T00:00:00",
        )


def test_document_upload_form_rejects_invalid_expiration_period() -> None:
    with pytest.raises(
        ValidationError,
        match="expires_at must be later than effective_at.",
    ):
        DocumentUploadForm(
            title="会员退款政策",
            domain="refund",
            policy_key="REFUND-POLICY",
            source_type=DocumentSourceType.OFFICIAL_POLICY,
            version_number=1,
            effective_at="2026-07-21T00:00:00+08:00",
            expires_at="2026-07-20T00:00:00+08:00",
        )


def test_document_upload_form_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        DocumentUploadForm(
            title="会员退款政策",
            domain="refund",
            policy_key="REFUND-POLICY",
            source_type=DocumentSourceType.OFFICIAL_POLICY,
            version_number=1,
            effective_at="2026-07-21T00:00:00+08:00",
            titel="故意拼错的字段",
        )
