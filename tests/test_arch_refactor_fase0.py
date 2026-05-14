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
    from app.db.database import get_connection
    conn = get_connection()
    row = conn.execute("PRAGMA journal_mode").fetchone()
    conn.close()
    assert row[0] == "wal"


def test_get_connection_sets_busy_timeout():
    from app.db.database import get_connection
    conn = get_connection()
    row = conn.execute("PRAGMA busy_timeout").fetchone()
    conn.close()
    assert int(row[0]) >= 5000


# ── 2. Settings: OPENCODE_CWD ─────────────────────────────────────────────────

def test_settings_has_opencode_cwd():
    from app.config import settings
    assert hasattr(settings, "OPENCODE_CWD"), "settings.OPENCODE_CWD must exist"
    assert isinstance(settings.OPENCODE_CWD, str)


def test_agent_call_opencode_uses_settings_cwd():
    import app.llm.agent as mod
    source = inspect.getsource(mod._call_opencode)
    assert "/home/frankpach/ibkr-bot" not in source, (
        "app/llm/agent.py still has hardcoded cwd — use settings.OPENCODE_CWD"
    )


def test_postmortem_call_opencode_uses_settings_cwd():
    import app.llm.postmortem as mod
    source = inspect.getsource(mod._call_opencode)
    assert "/home/frankpach/ibkr-bot" not in source, (
        "app/llm/postmortem.py still has hardcoded cwd — use settings.OPENCODE_CWD"
    )


def test_telegram_bot_call_opencode_uses_settings_cwd():
    import app.notifications.telegram_bot as mod
    source = inspect.getsource(mod._call_opencode)
    assert "/home/frankpach/ibkr-bot" not in source, (
        "app/notifications/telegram_bot.py still has hardcoded cwd — use settings.OPENCODE_CWD"
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


# ── 4. X-Control-Key auth dependency ─────────────────────────────────────────

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
