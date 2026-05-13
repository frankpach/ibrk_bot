# tests/conftest.py
"""Global pytest fixtures and setup."""
import sys
from pathlib import Path
from unittest.mock import MagicMock

# ---------------------------------------------------------------------------
# Stubs for missing dependencies (must be injected BEFORE any import that
# needs them, i.e. before test collection tries to import app.scanner.news).
# ---------------------------------------------------------------------------

# -- feedparser --------------------------------------------------------------
_feedparser_stub = MagicMock()
_feedparser_stub.parse.return_value = MagicMock(entries=[])
sys.modules["feedparser"] = _feedparser_stub

# -- fastmcp -----------------------------------------------------------------
class _FakeFastMCP:
    def __init__(self, **kwargs):
        self._tools = {}
    def tool(self, *args, **kwargs):
        def decorator(fn):
            self._tools[fn.__name__] = fn
            return fn
        return decorator
    def run(self, transport=None):
        pass

_fastmcp_stub = MagicMock()
_fastmcp_stub.FastMCP = _FakeFastMCP
sys.modules["fastmcp"] = _fastmcp_stub

# Ensure app package is importable
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


import pytest
from app.db.database import init_db, get_connection


@pytest.fixture(autouse=True)
def _init_test_db(tmp_path):
    """
    Every test gets a fresh in-memory SQLite DB with all tables.
    We temporarily override DB_PATH so the real file is never touched.
    """
    import app.db.database as db_mod
    import app.config.settings as settings_mod

    old_db_path = getattr(db_mod, "DB_PATH", None)
    test_db = str(tmp_path / "test.db")

    db_mod.DB_PATH = test_db
    settings_mod.DB_PATH = test_db

    init_db()

    # Seed symbol_config so validate_order / get_approved_symbols work
    conn = get_connection()
    conn.execute(
        "INSERT OR IGNORE INTO symbol_config (symbol, extra_indicators, approved, proposed_by, created_at) "
        "VALUES (?, ?, 1, ?, datetime('now'))",
        ("AAPL", "{}", "test"),
    )
    conn.commit()
    conn.close()

    yield

    # teardown: restore original path
    if old_db_path is not None:
        db_mod.DB_PATH = old_db_path
        settings_mod.DB_PATH = old_db_path
