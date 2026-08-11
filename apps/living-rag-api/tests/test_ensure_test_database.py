from __future__ import annotations

from sqlalchemy.engine import make_url

from scripts.ensure_test_database import (
    get_database_urls,
    to_psycopg_dsn,
)


def test_to_psycopg_dsn_removes_sqlalchemy_driver_suffix() -> None:
    url = make_url(
        "postgresql+psycopg://living_rag:secret@postgres:5432/living_rag"
    )

    assert to_psycopg_dsn(url) == (
        "postgresql://living_rag:secret@postgres:5432/living_rag"
    )


def test_get_database_urls_derives_dedicated_test_database(monkeypatch) -> None:
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+psycopg://living_rag:secret@postgres:5432/living_rag",
    )

    from app.core.config import get_settings

    get_settings.cache_clear()
    try:
        development_url, test_url = get_database_urls()
    finally:
        get_settings.cache_clear()

    assert development_url.database == "living_rag"
    assert test_url.database == "living_rag_test"

