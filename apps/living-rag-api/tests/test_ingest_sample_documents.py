"""Tests for the versioned Markdown document-ingestion script."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.document import Document, DocumentStatus, DocumentVersion
from app.models.document_chunk import DocumentChunk


API_ROOT = Path(__file__).resolve().parents[1]
INGEST_SCRIPT_PATH = API_ROOT / "scripts" / "ingest_sample_documents.py"


def _load_ingest_module() -> ModuleType:
    """Load the ingestion script as a testable module without running main."""

    module_spec = importlib.util.spec_from_file_location(
        "ingest_sample_documents_for_tests",
        INGEST_SCRIPT_PATH,
    )
    assert module_spec is not None
    assert module_spec.loader is not None

    module = importlib.util.module_from_spec(module_spec)
    sys.modules[module_spec.name] = module
    module_spec.loader.exec_module(module)
    return module


def _write_markdown(
    directory: Path,
    file_name: str,
    *,
    title: str,
    source_document_id: str,
    version: str,
    source_status: str,
    body: str,
) -> None:
    """Write one minimal Markdown source compatible with the ingest contract."""

    (directory / file_name).write_text(
        f"""# {title}

- 文档编号：{source_document_id}
- 文档类型：正式政策
- 版本：{version}
- 生效日期：2026-01-01
- 失效日期：无
- 文档状态：{source_status}
- 适用范围：pytest
- 维护部门：Quality Engineering

## 规则说明

{body}

## 优先级

以当前有效正式政策为准。
""",
        encoding="utf-8",
    )


def _ingest_sources(
    module: ModuleType,
    db_session: Session,
    sources: tuple[object, ...],
) -> object:
    """Run the script's persistence stages using the rollback-only test session."""

    stats = module.DocumentIngestionStats()
    documents_by_key = module.upsert_documents(db_session, sources, stats)
    module.ingest_document_versions(db_session, sources, documents_by_key, stats)
    return stats


def test_parse_policy_version_and_heading_chunks(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """REFUND-POLICY-V3 maps to one logical key and traceable heading chunks."""

    module = _load_ingest_module()
    monkeypatch.setattr(module, "DATA_DIRECTORY", tmp_path)

    _write_markdown(
        tmp_path,
        "refund_policy_v3.md",
        title="退款与退货政策（V3）",
        source_document_id="REFUND-POLICY-V3",
        version="v3",
        source_status="active",
        body="金卡会员在有效期限内可以申请退款。",
    )

    source = module.load_source_document("refund_policy_v3.md")

    assert source.document_key == "REFUND-POLICY"
    assert source.version_number == 3
    assert source.title == "退款与退货政策"
    assert source.source_document_status == "active"
    assert [chunk.chunk_index for chunk in source.chunks] == list(range(len(source.chunks)))
    assert source.chunks[0].heading == "文档元信息"
    assert any(chunk.heading == "规则说明" for chunk in source.chunks)
    assert all(chunk.char_start < chunk.char_end for chunk in source.chunks)


def test_ingest_invalid_document_is_archived_and_idempotent(
    db_session: Session,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An invalid source remains auditable but maps to an archived logical document."""

    module = _load_ingest_module()
    monkeypatch.setattr(module, "DATA_DIRECTORY", tmp_path)

    _write_markdown(
        tmp_path,
        "invalid_unlimited_refund_notice.md",
        title="错误退款公告",
        source_document_id="INVALID-UNLIMITED-REFUND-NOTICE",
        version="v1",
        source_status="invalid",
        body="本公告内容已经撤销，不得作为最终业务结论。",
    )

    source = module.load_source_document("invalid_unlimited_refund_notice.md")
    first_stats = _ingest_sources(module, db_session, (source,))

    assert first_stats.documents_created == 1
    assert first_stats.versions_created == 1
    assert first_stats.chunks_created == len(source.chunks)

    document = db_session.scalar(
        select(Document).where(
            Document.metadata_.op("->>")("document_key")
            == "INVALID-UNLIMITED-REFUND-NOTICE"
        )
    )
    assert document is not None
    assert document.status is DocumentStatus.ARCHIVED

    document_version = db_session.scalar(
        select(DocumentVersion).where(DocumentVersion.document_id == document.id)
    )
    assert document_version is not None
    assert document_version.metadata_["source_document_status"] == "invalid"

    second_stats = _ingest_sources(module, db_session, (source,))

    assert second_stats.documents_created == 0
    assert second_stats.documents_updated == 1
    assert second_stats.versions_created == 0
    assert second_stats.versions_unchanged == 1
    assert second_stats.chunks_created == 0
    assert second_stats.chunks_unchanged == len(source.chunks)

    assert db_session.scalar(select(func.count()).select_from(Document)) == 1
    assert db_session.scalar(select(func.count()).select_from(DocumentVersion)) == 1
    assert db_session.scalar(select(func.count()).select_from(DocumentChunk)) == len(source.chunks)


def test_reject_changed_content_for_existing_version(
    db_session: Session,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The same logical version cannot silently replace immutable content."""

    module = _load_ingest_module()
    monkeypatch.setattr(module, "DATA_DIRECTORY", tmp_path)

    _write_markdown(
        tmp_path,
        "refund_policy_v1.md",
        title="退款与退货政策（V1）",
        source_document_id="REFUND-POLICY-V1",
        version="v1",
        source_status="archived",
        body="第一版政策：普通会员适用七天退款期限。",
    )
    first_source = module.load_source_document("refund_policy_v1.md")
    _ingest_sources(module, db_session, (first_source,))

    _write_markdown(
        tmp_path,
        "refund_policy_v1.md",
        title="退款与退货政策（V1）",
        source_document_id="REFUND-POLICY-V1",
        version="v1",
        source_status="archived",
        body="错误修改：同一版本号下的内容已经被替换。",
    )
    changed_source = module.load_source_document("refund_policy_v1.md")

    stats = module.DocumentIngestionStats()
    documents_by_key = module.upsert_documents(
        db_session,
        (changed_source,),
        stats,
    )

    with pytest.raises(
        module.DocumentIngestionError,
        match="content hash differs from an existing immutable document version",
    ):
        module.ingest_document_versions(
            db_session,
            (changed_source,),
            documents_by_key,
            stats,
        )