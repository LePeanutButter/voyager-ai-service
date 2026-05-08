"""SQLAlchemy engine and connectivity checks (PostgreSQL / SQLite)."""

from __future__ import annotations

from typing import Generator, Optional

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import settings


class Base(DeclarativeBase):
    """Declarative base for future ORM models and Alembic."""

    pass


_engine: Optional[Engine] = None
SessionLocal: Optional[sessionmaker] = None


def init_db_engine() -> Engine:
    """Create a singleton engine and session factory if not already present."""
    global _engine, SessionLocal
    if _engine is not None:
        return _engine
    url = settings.resolved_database_url
    kwargs: dict = {"pool_pre_ping": True}
    if url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
    else:
        kwargs["pool_size"] = 5
        kwargs["max_overflow"] = 10
    _engine = create_engine(url, **kwargs)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_engine)
    return _engine


def get_engine() -> Engine:
    """Return the shared engine, initializing it on first use."""
    if _engine is None:
        return init_db_engine()
    return _engine


def check_db_connection() -> None:
    """Raises if the database is unreachable."""
    eng = get_engine()
    with eng.connect() as conn:
        conn.execute(text("SELECT 1"))


def init_runtime_tables() -> None:
    """Create runtime persistence tables required by services."""
    # Import registers ORM models on Base metadata.
    from app.db import runtime_models  # noqa: F401

    eng = get_engine()
    Base.metadata.create_all(bind=eng)


def get_db() -> Generator:
    """FastAPI dependency: yields a DB session (when SessionLocal is initialized)."""
    if SessionLocal is None:
        init_db_engine()
    assert SessionLocal is not None
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
