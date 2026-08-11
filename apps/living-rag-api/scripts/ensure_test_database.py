"""Create the dedicated PostgreSQL database used by the test suite."""

from __future__ import annotations

import sys
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core.config import get_settings


def _quote_identifier(value: str) -> str:
    """Quote a PostgreSQL identifier without accepting SQL syntax."""

    return '"' + value.replace('"', '""') + '"'


def ensure_test_database() -> str:
    """Create ``<application database>_test`` if it does not exist."""

    settings = get_settings()
    application_url = make_url(settings.database_url)

    if not application_url.database:
        raise RuntimeError("DATABASE_URL must include a database name.")
    if not application_url.username:
        raise RuntimeError("DATABASE_URL must include a database user.")

    test_database = f"{application_url.database}_test"
    admin_url = application_url.set(database="postgres")
    engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")

    try:
        with engine.connect() as connection:
            exists = connection.execute(
                text(
                    "SELECT 1 FROM pg_database "
                    "WHERE datname = :database_name"
                ),
                {"database_name": test_database},
            ).scalar()

            if exists is None:
                connection.exec_driver_sql(
                    "CREATE DATABASE "
                    f"{_quote_identifier(test_database)} OWNER "
                    f"{_quote_identifier(application_url.username)}"
                )
                print(f"Created test database: {test_database}")
            else:
                print(f"Test database already exists: {test_database}")
    finally:
        engine.dispose()

    return test_database


if __name__ == "__main__":
    ensure_test_database()
