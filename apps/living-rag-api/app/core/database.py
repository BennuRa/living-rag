from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings


settings = get_settings()

engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """Shared declarative base for every Living RAG ORM model."""


def get_db() -> Generator[Session, None, None]:
    """Yield one database session and close it after the caller finishes."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()