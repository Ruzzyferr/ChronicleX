"""PostgreSQL engine, sessions, schema creation."""

from __future__ import annotations

import logging
from collections.abc import Generator
from contextlib import contextmanager

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from storage.models import Base

logger = logging.getLogger(__name__)

_engine: Engine | None = None
_SessionLocal: sessionmaker[Session] | None = None
_schema_checked: bool = False


def _is_postgresql(url: str) -> bool:
    u = url.lower()
    return u.startswith("postgresql://") or u.startswith("postgresql+psycopg2://")


def get_engine(database_url: str) -> Engine:
    global _engine
    if _engine is None:
        if not database_url or database_url.strip() == "":
            raise ValueError("DATABASE_URL is empty")
        if not _is_postgresql(database_url):
            raise ValueError(
                "DATABASE_URL must be a PostgreSQL URL "
                "(postgresql://... or postgresql+psycopg2://...)"
            )
        _engine = create_engine(
            database_url,
            pool_pre_ping=True,
            future=True,
        )
        logger.debug("SQLAlchemy engine created for PostgreSQL")
    return _engine


def get_session_factory(database_url: str) -> sessionmaker[Session]:
    global _SessionLocal
    if _SessionLocal is None:
        engine = get_engine(database_url)
        _SessionLocal = sessionmaker(
            bind=engine,
            autoflush=False,
            autocommit=False,
            expire_on_commit=False,
            future=True,
        )
    return _SessionLocal


def ensure_schema(database_url: str) -> None:
    """Create tables if they do not exist (dev-friendly; use Alembic in production)."""
    global _schema_checked
    if _schema_checked:
        return
    engine = get_engine(database_url)
    Base.metadata.create_all(bind=engine)
    _schema_checked = True
    logger.info("Database schema ensured (create_all)")


def ping_database(database_url: str) -> None:
    engine = get_engine(database_url)
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))


@contextmanager
def session_scope(database_url: str) -> Generator[Session, None, None]:
    SessionLocal = get_session_factory(database_url)
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def reset_engine_cache() -> None:
    """Test helper: clear cached engine/session."""
    global _engine, _SessionLocal, _schema_checked
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _SessionLocal = None
    _schema_checked = False
