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
from unittest.mock import patch
from app.infrastructure.db.compat import init_db, get_connection


@pytest.fixture(autouse=True)
def _mock_notifications():
    """Prevent any test from hitting Telegram or starting the notification thread."""
    import app.notifications.queue as nq_mod
    with patch("app.notifications.queue.enqueue_notification"), \
         patch("app.notifications.queue.get_notification_queue"):
        old_instance = nq_mod._queue_instance
        nq_mod._queue_instance = None
        yield
        nq_mod._queue_instance = old_instance


@pytest.fixture(autouse=True)
def _init_test_db(tmp_path, monkeypatch):
    """
    Every test gets a fresh isolated SQLite DB.
    DATABASE_URL is overridden via monkeypatch so get_database_url() and
    get_connection() both see the per-test path, even under pytest-xdist.
    The engine singleton is reset before and after so workers don't share it.
    """
    import app.infrastructure.db.compat as db_mod
    import app.infrastructure.db.engine as engine_mod
    import app.config.settings as settings_mod

    test_db = str(tmp_path / "test.db")
    test_url = f"sqlite:///{test_db}"

    # Override every path the code uses to resolve the DB
    monkeypatch.setenv("DATABASE_URL", test_url)
    monkeypatch.setattr(db_mod, "DB_PATH", test_db, raising=False)
    monkeypatch.setattr(settings_mod, "DB_PATH", test_db, raising=False)
    monkeypatch.setattr(engine_mod, "DB_PATH", test_db, raising=False)

    # Reset the cached engine so this worker gets a fresh one for this test
    engine_mod.reset_engine()

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

    engine_mod.reset_engine()
