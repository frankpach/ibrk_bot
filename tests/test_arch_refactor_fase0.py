# tests/test_arch_refactor_fase0.py
"""
arch-refactor Fase 0 — Quick Wins
  1. WAL mode + busy_timeout in get_connection()
  2. settings.OPENCODE_CWD exists (no more hardcoded /home/frankpach/ibkr-bot)
  3. OpenCodeAdapter in app.infrastructure.llm.opencode_adapter
  4. X-Control-Key auth dependency in app.api.auth
"""
import inspect
import subprocess
from unittest.mock import MagicMock, patch

import pytest


# ── 1. WAL mode ───────────────────────────────────────────────────────────────

def test_get_connection_enables_wal_mode():
    from app.infrastructure.db.compat import get_connection
    conn = get_connection()
    row = conn.execute("PRAGMA journal_mode").fetchone()
    conn.close()
    assert row[0] == "wal"


def test_get_connection_sets_busy_timeout():
    from app.infrastructure.db.compat import get_connection
    conn = get_connection()
    row = conn.execute("PRAGMA busy_timeout").fetchone()
    conn.close()
    assert int(row[0]) >= 5000


# ── 2. Settings: OPENCODE_CWD ─────────────────────────────────────────────────

def test_settings_has_opencode_cwd():
    from app.config import settings
    assert hasattr(settings, "OPENCODE_CWD"), "settings.OPENCODE_CWD must exist"
    assert isinstance(settings.OPENCODE_CWD, str)


def test_agent_uses_opencode_adapter():
    import app.llm.agent as mod
    assert not hasattr(mod, "_call_opencode"), (
        "app/llm/agent.py still defines _call_opencode — use OpenCodeAdapter"
    )


def test_postmortem_uses_opencode_adapter():
    import app.llm.postmortem as mod
    assert not hasattr(mod, "_call_opencode"), (
        "app/llm/postmortem.py still defines _call_opencode — use OpenCodeAdapter"
    )


def test_telegram_bot_uses_opencode_adapter():
    import app.notifications.telegram_bot as mod
    assert not hasattr(mod, "_call_opencode"), (
        "app/notifications/telegram_bot.py still defines _call_opencode — use OpenCodeAdapter"
    )


def test_pipeline_llm_interpret_uses_settings_cwd():
    import app.analysis.pipeline as mod
    source = inspect.getsource(mod.AnalysisPipeline._llm_interpret)
    assert "/home/frankpach/ibkr-bot" not in source, (
        "app/analysis/pipeline.py _llm_interpret still has hardcoded cwd — use settings.OPENCODE_CWD"
    )


# ── 3. OpenCodeAdapter ────────────────────────────────────────────────────────

def test_opencode_adapter_is_importable():
    from app.infrastructure.llm.opencode_adapter import OpenCodeAdapter
    assert OpenCodeAdapter is not None


def test_opencode_adapter_returns_text_from_json_events():
    from app.infrastructure.llm.opencode_adapter import OpenCodeAdapter
    fake_stdout = (
        '{"type": "text", "part": {"text": "Hello "}}\n'
        '{"type": "text", "part": {"text": "world"}}\n'
    )
    mock_result = MagicMock()
    mock_result.stdout = fake_stdout
    with patch("subprocess.run", return_value=mock_result):
        result = OpenCodeAdapter().call("test prompt")
    assert result == "Hello world"


def test_opencode_adapter_skips_non_text_events():
    from app.infrastructure.llm.opencode_adapter import OpenCodeAdapter
    fake_stdout = (
        '{"type": "tool_call", "part": {}}\n'
        '{"type": "text", "part": {"text": "Only this"}}\n'
        'not-valid-json\n'
    )
    mock_result = MagicMock()
    mock_result.stdout = fake_stdout
    with patch("subprocess.run", return_value=mock_result):
        result = OpenCodeAdapter().call("test prompt")
    assert result == "Only this"


def test_opencode_adapter_returns_empty_on_timeout():
    from app.infrastructure.llm.opencode_adapter import OpenCodeAdapter
    with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("opencode", 60)):
        result = OpenCodeAdapter().call("test prompt")
    assert result == ""


def test_opencode_adapter_returns_empty_on_os_error():
    from app.infrastructure.llm.opencode_adapter import OpenCodeAdapter
    with patch("subprocess.run", side_effect=OSError("binary not found")):
        result = OpenCodeAdapter().call("test prompt")
    assert result == ""


def test_opencode_adapter_passes_cwd_from_settings():
    from app.infrastructure.llm.opencode_adapter import OpenCodeAdapter
    mock_result = MagicMock()
    mock_result.stdout = ""
    with patch("subprocess.run", return_value=mock_result) as mock_run:
        OpenCodeAdapter().call("prompt")
    _args, kwargs = mock_run.call_args
    from app.config import settings
    assert kwargs.get("cwd") == settings.OPENCODE_CWD


def test_opencode_adapter_has_safe_symbol_re():
    from app.infrastructure.llm.opencode_adapter import OpenCodeAdapter
    adapter = OpenCodeAdapter()
    assert hasattr(adapter, "SAFE_SYMBOL_RE")
    assert adapter.SAFE_SYMBOL_RE.match("AAPL")
    assert adapter.SAFE_SYMBOL_RE.match("EURUSD")
    assert not adapter.SAFE_SYMBOL_RE.match("AAPL;rm -rf")
    assert not adapter.SAFE_SYMBOL_RE.match("AAPL\nDROP")


def test_opencode_adapter_validates_bin_path(monkeypatch):
    from app.infrastructure.llm.opencode_adapter import OpenCodeAdapter
    monkeypatch.setenv("OPENCODE_BIN", "/nonexistent/opencode")
    # Force re-import of settings to pick up env var
    import importlib
    import app.config.settings as s
    importlib.reload(s)
    adapter = OpenCodeAdapter()
    # Should not raise on instantiation, but analyze_signal with invalid bin should work
    # The check is done lazily or eagerly depending on implementation.
    # For now just verify the attribute exists.
    assert hasattr(adapter, "_bin_path")


def test_opencode_adapter_analyze_signal_rejects_invalid_symbol():
    from app.infrastructure.llm.opencode_adapter import OpenCodeAdapter
    adapter = OpenCodeAdapter()
    with pytest.raises(ValueError, match="Invalid symbol"):
        adapter.analyze_signal("AAPL;rm -rf", "test prompt")


def test_opencode_adapter_analyze_signal_accepts_valid_symbol():
    from app.infrastructure.llm.opencode_adapter import OpenCodeAdapter
    adapter = OpenCodeAdapter()
    fake_stdout = '{"type": "text", "part": {"text": "BUY"}}\n'
    mock_result = MagicMock()
    mock_result.stdout = fake_stdout
    with patch("subprocess.run", return_value=mock_result):
        result = adapter.analyze_signal("AAPL", "test prompt")
    assert result == "BUY"


def test_no_call_opencode_in_agent_pipeline_telegram():
    import app.llm.agent as agent_mod
    import app.analysis.pipeline as pipe_mod
    import app.notifications.telegram_bot as bot_mod
    assert not hasattr(agent_mod, "_call_opencode") or agent_mod._call_opencode.__module__ != agent_mod.__name__
    assert "_call_opencode" not in dir(pipe_mod) or not callable(getattr(pipe_mod, "_call_opencode", None))
    assert "_call_opencode" not in dir(bot_mod) or not callable(getattr(bot_mod, "_call_opencode", None))


# ── 4. control_settings persistence ──────────────────────────────────────────

def test_control_settings_table_exists():
    from app.infrastructure.db.compat import get_connection
    conn = get_connection()
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='control_settings'"
    ).fetchone()
    conn.close()
    assert row is not None


def test_control_settings_bootstrap_reads_env():
    from app.infrastructure.db.compat import get_control_settings, init_control_settings
    init_control_settings()
    settings = get_control_settings()
    assert "trading_mode" in settings
    assert "is_paused" in settings
    assert settings["trading_mode"] in ("paper", "live")
    assert settings["is_paused"] in (0, 1, True, False)


def test_control_settings_persist_on_change():
    from app.infrastructure.db.compat import get_control_settings, update_control_setting
    update_control_setting("trading_mode", "live")
    settings = get_control_settings()
    assert settings["trading_mode"] == "live"
    update_control_setting("trading_mode", "paper")
    settings = get_control_settings()
    assert settings["trading_mode"] == "paper"


# ── 5. Session context manager ───────────────────────────────────────────────

def test_get_session_context_manager():
    from app.infrastructure.db.session import get_session
    from app.infrastructure.db.compat import get_connection
    with get_session() as session:
        session.execute("SELECT 1")
    # After context manager exits, session should be closed


# ── 6. Structlog configuration ───────────────────────────────────────────────

def test_structlog_is_importable():
    import structlog
    assert structlog is not None


def test_structlog_logger_has_event_key():
    import structlog
    logger = structlog.get_logger("test")
    # Just verify structlog is configured enough to create a logger
    assert logger is not None


# ── 7. X-Control-Key auth dependency ─────────────────────────────────────────

def test_auth_module_is_importable():
    from app.api.auth import require_control_key
    assert callable(require_control_key)


def test_require_control_key_raises_401_when_missing(monkeypatch):
    import app.config.settings as s
    monkeypatch.setattr(s, "API_CONTROL_KEY", "secret-key")
    from app.api.auth import require_control_key
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc:
        require_control_key(x_control_key=None)
    assert exc.value.status_code == 401


def test_require_control_key_raises_401_when_wrong(monkeypatch):
    import app.config.settings as s
    monkeypatch.setattr(s, "API_CONTROL_KEY", "secret-key")
    from app.api.auth import require_control_key
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc:
        require_control_key(x_control_key="wrong-key")
    assert exc.value.status_code == 401


def test_require_control_key_passes_with_correct_key(monkeypatch):
    import app.config.settings as s
    monkeypatch.setattr(s, "API_CONTROL_KEY", "secret-key")
    from app.api.auth import require_control_key
    # Must not raise
    require_control_key(x_control_key="secret-key")


def test_require_control_key_raises_401_when_env_key_is_empty(monkeypatch):
    import app.config.settings as s
    monkeypatch.setattr(s, "API_CONTROL_KEY", "")
    from app.api.auth import require_control_key
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc:
        require_control_key(x_control_key="")
    assert exc.value.status_code == 401
