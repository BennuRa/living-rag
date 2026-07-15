"""Shared PostgreSQL test-database fixtures for Living RAG."""

from collections.abc import Generator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine, URL, make_url
from sqlalchemy.orm import Session

import app.models  # Registers all ORM models on Base.metadata.
from app.core.config import get_settings
from app.core.database import Base


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
def test_engine() -> Generator[Engine, None, None]:
    """Create the disposable schema once in the dedicated PostgreSQL test database."""
    engine = create_engine(_get_test_database_url(), pool_pre_ping=True)
    Base.metadata.create_all(bind=engine)

    try:
        yield engine
    finally:
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


@pytest.fixture
def db_session(test_engine: Engine) -> Generator[Session, None, None]:
    """Provide one rollback-only transaction, isolated from every other test."""
    connection = test_engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")

    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()
