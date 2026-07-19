"""Shared PostgreSQL test-database fixtures for Living RAG."""

from __future__ import annotations

import os
from collections.abc import Generator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine, URL, make_url
from sqlalchemy.orm import Session

from app.core.config import get_settings


API_ROOT = Path(__file__).resolve().parents[1]
ALEMBIC_INI_PATH = API_ROOT / "alembic.ini"
def _reset_test_public_schema(test_database_url: URL) -> None:
    """Reset only the test database public schema before Alembic upgrades it."""

    engine = create_engine(
        test_database_url,
        isolation_level="AUTOCOMMIT",
        pool_pre_ping=True,
    )

    try:
        with engine.connect() as connection:
            connection.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
            connection.execute(text("CREATE SCHEMA public"))
    finally:
        engine.dispose()

def _get_test_database_url() -> URL:
    """Return a safe, dedicated PostgreSQL database URL for tests only."""

    settings = get_settings()
    development_url = make_url(settings.database_url)

    if not development_url.database:
        raise RuntimeError("DATABASE_URL must include a database name.")

    test_url = development_url.set(database=f"{development_url.database}_test")

    if test_url.database == development_url.database:
        raise RuntimeError(
            "The derived test database must be distinct from DATABASE_URL."
        )

    if not test_url.database or not test_url.database.endswith("_test"):
        raise RuntimeError(
            "The derived test database name must end in '_test'."
        )

    return test_url


@pytest.fixture(scope="session")
def test_database_url() -> URL:
    """Expose the dedicated test database URL to session-scoped fixtures."""

    return _get_test_database_url()


@pytest.fixture(scope="session")
def migrated_test_database(
    test_database_url: URL,
) -> Generator[None, None, None]:
    """Create and remove the test schema through the Alembic migration chain."""

    original_database_url = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = test_database_url.render_as_string(
        hide_password=False
    )
    get_settings.cache_clear()

    alembic_config = Config(str(ALEMBIC_INI_PATH))
    migration_completed = False

    try:
        _reset_test_public_schema(test_database_url)
        command.upgrade(alembic_config, "head")
        migration_completed = True
        yield
    finally:
        try:
            if migration_completed:
                command.downgrade(alembic_config, "base")
        finally:
            if original_database_url is None:
                os.environ.pop("DATABASE_URL", None)
            else:
                os.environ["DATABASE_URL"] = original_database_url

            get_settings.cache_clear()


@pytest.fixture(scope="session")
def test_engine(
    test_database_url: URL,
    migrated_test_database: None,
) -> Generator[Engine, None, None]:
    """Create one engine for the Alembic-managed test schema."""

    engine = create_engine(test_database_url, pool_pre_ping=True)

    try:
        yield engine
    finally:
        engine.dispose()


@pytest.fixture
def db_session(test_engine: Engine) -> Generator[Session, None, None]:
    """Provide one rollback-only transaction isolated from every other test."""

    connection = test_engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")

    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()