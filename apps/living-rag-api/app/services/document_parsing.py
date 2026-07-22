from io import BytesIO
from pathlib import Path

from pypdf import PdfReader
from pypdf.errors import PdfReadError


def clean_text(text: str) -> str:
    text = text.replace("\r\n", "\n")
    text = text.replace("\r", "\n")
    lines = text.splitlines()
    cleaned_lines = []

    for line in lines:
        cleaned_lines.append(line.rstrip())

    cleaned_text = "\n".join(cleaned_lines).strip()

    if not cleaned_text:
        raise ValueError("Document content must not be blank.")

    return cleaned_text


def decode_utf8(content: bytes) -> str:
    try:
        return content.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ValueError("Document content must be valid UTF-8.") from error


def parse_text_content(content: bytes) -> str:
    return clean_text(decode_utf8(content))


def parse_uploaded_content(filename: str, content: bytes) -> str:
    suffix = Path(filename).suffix.lower()

    if suffix in {".md", ".markdown", ".txt"}:
        return parse_text_content(content)

    if suffix == ".pdf":
        return parse_pdf_content(content)

    raise ValueError("Unsupported document type.")


def parse_pdf_content(content: bytes) -> str:
    try:
        pdf_stream = BytesIO(content)
        reader = PdfReader(pdf_stream)
        page_texts: list[str] = []
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text and page_text.strip():
                page_texts.append(page_text)

        if not page_texts:
            raise ValueError("PDF contains no extractable text.")

        return clean_text("\n".join(page_texts))
    except PdfReadError as error:
        raise ValueError("Failed to parse PDF content.") from error
