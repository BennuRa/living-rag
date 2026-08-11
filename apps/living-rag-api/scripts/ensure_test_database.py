"""Ensure that the dedicated PostgreSQL database used by pytest exists.

Run inside the API container:

    python scripts/ensure_test_database.py

The command is idempotent. It creates ``living_rag_test`` when necessary and
does nothing when the database already exists. It never drops or migrates a
database.
"""

from __future__ import annotations

import sys
from pathlib import Path

import psycopg
from psycopg import sql
from sqlalchemy.engine import URL, make_url

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core.config import get_settings


class TestDatabaseInitializationError(RuntimeError):
    """Raised when the dedicated pytest database cannot be prepared."""


def to_psycopg_dsn(url: URL) -> str:
    """Convert a SQLAlchemy URL into a DSN accepted by psycopg."""

    return url.set(drivername="postgresql").render_as_string(
        hide_password=False,
    )


def get_database_urls() -> tuple[URL, URL]:
    """Return the development and derived test database URLs."""

    development_url = make_url(get_settings().database_url)

    if not development_url.database:
        raise TestDatabaseInitializationError(
            "DATABASE_URL must include a database name."
        )

    test_url = development_url.set(database=f"{development_url.database}_test")

    if test_url.database == development_url.database:
        raise TestDatabaseInitializationError(
            "The derived test database must be distinct from DATABASE_URL."
        )

    if not test_url.database or not test_url.database.endswith("_test"):
        raise TestDatabaseInitializationError(
            "The derived test database name must end in '_test'."
        )

    return development_url, test_url


def ensure_test_database() -> bool:
    """Create the derived test database when it does not already exist.

    Returns:
        ``True`` when a database was created, otherwise ``False``.

    Raises:
        TestDatabaseInitializationError: If the database configuration or
            PostgreSQL operation is invalid.
    """

    development_url, test_url = get_database_urls()
    database_name = test_url.database
    owner_name = development_url.username

    if not database_name or not owner_name:
        raise TestDatabaseInitializationError(
            "DATABASE_URL must include both database and username."
        )

    try:
        with psycopg.connect(
            to_psycopg_dsn(development_url),
            autocommit=True,
        ) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT 1 FROM pg_database WHERE datname = %s",
                    (database_name,),
                )

                if cursor.fetchone() is not None:
                    return False

                cursor.execute(
                    sql.SQL("CREATE DATABASE {} OWNER {}").format(
                        sql.Identifier(database_name),
                        sql.Identifier(owner_name),
                    )
                )
    except Exception as error:
        raise TestDatabaseInitializationError(
            f"Could not ensure test database {database_name!r}: {error}"
        ) from error

    return True


def main() -> None:
    """Prepare the pytest database and print a stable result."""

    try:
        created = ensure_test_database()
    except TestDatabaseInitializationError as error:
        print(f"Test database initialization failed: {error}", file=sys.stderr)
        raise SystemExit(1) from error

    database_name = get_database_urls()[1].database
    action = "created" if created else "already exists"
    print(f"Test database {database_name}: {action}.")


if __name__ == "__main__":
    main()
