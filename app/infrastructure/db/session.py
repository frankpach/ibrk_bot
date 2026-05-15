# app/infrastructure/db/session.py
"""Session context manager using the legacy compat connection."""
from collections.abc import Generator
from contextlib import contextmanager
from typing import Any

from app.infrastructure.db.compat import get_connection


@contextmanager
def get_session() -> Generator[Any, None, None]:
    """Yield a DB connection that auto-commits on success or rolls back on exception."""
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
