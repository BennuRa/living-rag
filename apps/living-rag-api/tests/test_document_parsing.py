from io import BytesIO
import app.services.document_parsing as document_parsing
from pypdf import PdfWriter
from app.services.document_parsing import (
    clean_text,
    decode_utf8,
    parse_pdf_content,
    parse_text_content,
    parse_uploaded_content,
)
import pytest


def test_clean_text_normalizes_line_endings_and_trailing_whitespace() -> None:
    raw_text = "  第一行   \r\n第二行\t\r第三行  \n"

    cleaned = clean_text(raw_text)

    assert cleaned == "第一行\n第二行\n第三行"


def test_clean_text_rejects_blank_content() -> None:
    with pytest.raises(
        ValueError,
        match="Document content must not be blank.",
    ):
        clean_text(" \t\r\n  \n ")


def test_clean_text_preserves_markdown_structure() -> None:
    raw_text = "  # 退款政策  \n\n## 申请条件\n用户需要在签收后七天内申请退款。  "

    cleaned = clean_text(raw_text)

    assert cleaned == "# 退款政策\n\n## 申请条件\n用户需要在签收后七天内申请退款。"


def test_decode_utf8_decodes_valid_text() -> None:
    content = "会员退款政策".encode("utf-8")

    decoded = decode_utf8(content)

    assert decoded == "会员退款政策"


def test_decode_utf8_rejects_invalid_bytes() -> None:
    with pytest.raises(
        ValueError,
        match="Document content must be valid UTF-8.",
    ):
        decode_utf8(b"\xff\xfe\xfa")


def test_parse_text_content_decodes_and_cleans() -> None:
    content = "  # 退款政策  \r\n\r\n正文内容。  ".encode("utf-8")

    parsed = parse_text_content(content)

    assert parsed == "# 退款政策\n\n正文内容。"


def test_parse_uploaded_content_accepts_markdown() -> None:
    content = "  # 退款政策  \r\n\r\n正文内容。  ".encode("utf-8")

    parsed = parse_uploaded_content("refund_policy.md", content)

    assert parsed == "# 退款政策\n\n正文内容。"


def test_parse_uploaded_content_accepts_text_case_insensitively() -> None:
    content = "会员权益说明".encode("utf-8")

    parsed = parse_uploaded_content("MEMBERSHIP.TXT", content)

    assert parsed == "会员权益说明"


def test_parse_uploaded_content_rejects_unsupported_type() -> None:
    with pytest.raises(
        ValueError,
        match="Unsupported document type.",
    ):
        parse_uploaded_content("policy.docx", b"not a real docx")


def test_parse_pdf_content_rejects_invalid_pdf() -> None:
    with pytest.raises(
        ValueError,
        match="Failed to parse PDF content.",
    ):
        parse_pdf_content(b"this is not a valid pdf")


def test_parse_pdf_content_rejects_pdf_without_extractable_text() -> None:
    pdf_buffer = BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    writer.write(pdf_buffer)

    with pytest.raises(
        ValueError,
        match="PDF contains no extractable text.",
    ):
        parse_pdf_content(pdf_buffer.getvalue())


def test_parse_uploaded_content_dispatches_pdf(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_parse_pdf_content(content: bytes) -> str:
        assert content == b"pdf bytes"
        return "提取出的 PDF 文本"

    monkeypatch.setattr(
        document_parsing,
        "parse_pdf_content",
        fake_parse_pdf_content,
    )

    parsed = document_parsing.parse_uploaded_content(
        "POLICY.PDF",
        b"pdf bytes",
    )

    assert parsed == "提取出的 PDF 文本"
