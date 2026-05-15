# app/infrastructure/db/engine.py
"""SQLAlchemy engine factory with dual backend support (SQLite / PostgreSQL)."""
from __future__ import annotations

import os

from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from app.config.settings import DB_PATH

_engine = None


def get_database_url() -> str:
    """Resolve database URL.

    Precedence:
        1. ``DATABASE_URL`` environment variable.
        2. Default ``sqlite:///{DB_PATH}``.
    """
    env_url = os.getenv("DATABASE_URL")
    if env_url:
        return env_url
    return f"sqlite:///{DB_PATH}"


def _is_postgres(url: str) -> bool:
    return url.startswith("postgresql") or url.startswith("postgres://")


def get_engine(database_url: str | None = None):
    """Return a cached SQLAlchemy engine.

    Uses ``pool_size=5, max_overflow=10`` for PostgreSQL and
    ``StaticPool`` with ``check_same_thread=False`` for SQLite.
    """
    global _engine
    if _engine is not None:
        return _engine

    url = database_url or get_database_url()

    if _is_postgres(url):
        _engine = create_engine(
            url,
            pool_size=5,
            max_overflow=10,
            echo=False,
        )
    else:
        _engine = create_engine(
            url,
            poolclass=StaticPool,
            connect_args={"check_same_thread": False},
            echo=False,
        )
    return _engine


def reset_engine() -> None:
    """Dispose and clear the cached engine."""
    global _engine
    if _engine is not None:
        _engine.dispose()
    _engine = None
