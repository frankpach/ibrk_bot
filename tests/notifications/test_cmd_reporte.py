# tests/notifications/test_cmd_reporte.py
"""Tests for cmd_reporte (async fire-and-forget report command),
updated cmd_ayuda with dynamic markets, and _get_operable_market_keys."""
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.notifications.telegram_bot import (
    cmd_reporte,
    cmd_ayuda,
    _get_operable_market_keys,
    _MARKET_LABELS,
    _MARKET_SCHEDULE,
)

OWNER_ID = "123"


def make_update(chat_id=OWNER_ID):
    update = MagicMock()
    update.effective_chat.id = chat_id
    update.message.reply_text = AsyncMock()
    return update


def make_ctx(args=None):
    ctx = MagicMock()
    ctx.args = args or []
    return ctx


# ---------------------------------------------------------------------------
# _get_operable_market_keys
# ---------------------------------------------------------------------------

def test_get_operable_returns_known_keys_when_all_available():
    fake_perms = [
        {"key": "STK_US",  "available": True},
        {"key": "FUT_US",  "available": True},
        {"key": "CASH_FX", "available": True},
        {"key": "CRYPTO",  "available": True},
    ]
    with patch("app.notifications.telegram_bot.get_market_permissions", return_value=fake_perms, create=True), \
         patch("app.infrastructure.db.compat.get_market_permissions", return_value=fake_perms):
        keys = _get_operable_market_keys()
    assert "STK_US" in keys
    assert "FUT_US" in keys


def test_get_operable_filters_unavailable():
    fake_perms = [
        {"key": "STK_US",  "available": True},
        {"key": "FUT_US",  "available": False},
        {"key": "CASH_FX", "available": False},
        {"key": "CRYPTO",  "available": True},
    ]
    with patch("app.infrastructure.db.compat.get_market_permissions", return_value=fake_perms):
        keys = _get_operable_market_keys()
    assert "STK_US" in keys
    assert "CRYPTO" in keys
    assert "FUT_US" not in keys
    assert "CASH_FX" not in keys


def test_get_operable_fallback_on_db_error():
    with patch("app.infrastructure.db.compat.get_market_permissions", side_effect=Exception("db down")):
        keys = _get_operable_market_keys()
    assert isinstance(keys, list)
    assert len(keys) > 0


def test_get_operable_fallback_when_table_empty():
    """Empty permissions table must return full default list, not []."""
    with patch("app.infrastructure.db.compat.get_market_permissions", return_value=[]):
        keys = _get_operable_market_keys()
    assert "STK_US" in keys
    assert len(keys) > 0


# ---------------------------------------------------------------------------
# cmd_ayuda — dynamic market section
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cmd_ayuda_contains_reporte_command():
    update = make_update()
    ctx = make_ctx()
    with patch("app.notifications.telegram_bot.TELEGRAM_CHAT_ID", OWNER_ID), \
         patch("app.notifications.telegram_bot._get_operable_market_keys", return_value=["STK_US", "CRYPTO"]):
        await cmd_ayuda(update, ctx)
    text = update.message.reply_text.call_args[0][0]
    assert "/reporte" in text


@pytest.mark.asyncio
async def test_cmd_ayuda_lists_operable_markets():
    update = make_update()
    ctx = make_ctx()
    with patch("app.notifications.telegram_bot.TELEGRAM_CHAT_ID", OWNER_ID), \
         patch("app.notifications.telegram_bot._get_operable_market_keys", return_value=["STK_US", "FUT_US"]):
        await cmd_ayuda(update, ctx)
    text = update.message.reply_text.call_args[0][0]
    assert "STK_US" in text
    assert "FUT_US" in text


@pytest.mark.asyncio
async def test_cmd_ayuda_shows_schedule_hints():
    update = make_update()
    ctx = make_ctx()
    with patch("app.notifications.telegram_bot.TELEGRAM_CHAT_ID", OWNER_ID), \
         patch("app.notifications.telegram_bot._get_operable_market_keys", return_value=["STK_US"]):
        await cmd_ayuda(update, ctx)
    text = update.message.reply_text.call_args[0][0]
    # Schedule hint for STK_US must appear somewhere in the help text
    assert "09:15" in text


@pytest.mark.asyncio
async def test_cmd_ayuda_still_contains_core_commands():
    update = make_update()
    ctx = make_ctx()
    with patch("app.notifications.telegram_bot.TELEGRAM_CHAT_ID", OWNER_ID), \
         patch("app.notifications.telegram_bot._get_operable_market_keys", return_value=[]):
        await cmd_ayuda(update, ctx)
    text = update.message.reply_text.call_args[0][0]
    for cmd in ("/estado", "/analizar", "/cerrar", "/posiciones"):
        assert cmd in text, f"Missing {cmd} in /ayuda output"


# ---------------------------------------------------------------------------
# cmd_reporte — owner guard
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cmd_reporte_blocked_for_non_owner():
    update = make_update(chat_id="999")
    ctx = make_ctx()
    with patch("app.notifications.telegram_bot.TELEGRAM_CHAT_ID", OWNER_ID):
        await cmd_reporte(update, ctx)
    update.message.reply_text.assert_not_called()


# ---------------------------------------------------------------------------
# cmd_reporte — invalid market key
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cmd_reporte_unknown_market_shows_error():
    update = make_update()
    ctx = make_ctx(args=["INVALID_MKT"])
    with patch("app.notifications.telegram_bot.TELEGRAM_CHAT_ID", OWNER_ID), \
         patch("app.notifications.telegram_bot._get_operable_market_keys", return_value=["STK_US"]):
        await cmd_reporte(update, ctx)
    text = update.message.reply_text.call_args[0][0].lower()
    assert "no reconocido" in text or "invalid_mkt" in text


# ---------------------------------------------------------------------------
# cmd_reporte — fire-and-forget success path
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cmd_reporte_sends_ack_then_result():
    """Bot must reply twice: 1) immediate ack, 2) report link when done."""
    update = make_update()
    ctx = make_ctx(args=["STK_US"])

    future = asyncio.get_event_loop().create_future()
    future.set_result(77)  # fake report_id

    mock_loop = MagicMock()
    mock_loop.run_in_executor = AsyncMock(return_value=77)

    with patch("app.notifications.telegram_bot.TELEGRAM_CHAT_ID", OWNER_ID), \
         patch("app.notifications.telegram_bot._get_operable_market_keys", return_value=["STK_US"]), \
         patch("asyncio.get_event_loop", return_value=mock_loop), \
         patch("app.container.get_container", MagicMock()), \
         patch("app.config.settings.API_BASE", "http://127.0.0.1:8000"):
        await cmd_reporte(update, ctx)

    assert update.message.reply_text.call_count == 2
    first_call = update.message.reply_text.call_args_list[0][0][0]
    second_call = update.message.reply_text.call_args_list[1][0][0]
    assert "generando" in first_call.lower() or "⏳" in first_call
    assert "listo" in second_call.lower() or "77" in second_call


@pytest.mark.asyncio
async def test_cmd_reporte_no_args_auto_selects_market():
    """Without args, the command should still pick a market and proceed."""
    update = make_update()
    ctx = make_ctx(args=[])

    mock_loop = MagicMock()
    mock_loop.run_in_executor = AsyncMock(return_value=10)

    with patch("app.notifications.telegram_bot.TELEGRAM_CHAT_ID", OWNER_ID), \
         patch("app.notifications.telegram_bot._get_operable_market_keys", return_value=["STK_US"]), \
         patch("asyncio.get_event_loop", return_value=mock_loop), \
         patch("app.container.get_container", MagicMock()), \
         patch("app.config.settings.API_BASE", "http://127.0.0.1:8000"):
        await cmd_reporte(update, ctx)

    # Should reply at least once (ack)
    assert update.message.reply_text.call_count >= 1


@pytest.mark.asyncio
async def test_cmd_reporte_handles_report_generation_failure():
    """When run_in_executor returns None, bot notifies of failure gracefully."""
    update = make_update()
    ctx = make_ctx(args=["STK_US"])

    mock_loop = MagicMock()
    mock_loop.run_in_executor = AsyncMock(return_value=None)

    with patch("app.notifications.telegram_bot.TELEGRAM_CHAT_ID", OWNER_ID), \
         patch("app.notifications.telegram_bot._get_operable_market_keys", return_value=["STK_US"]), \
         patch("asyncio.get_event_loop", return_value=mock_loop), \
         patch("app.container.get_container", MagicMock()):
        await cmd_reporte(update, ctx)

    assert update.message.reply_text.call_count == 2
    second_text = update.message.reply_text.call_args_list[1][0][0].lower()
    assert "no se pudo" in second_text or "diagnostico" in second_text


@pytest.mark.asyncio
async def test_cmd_reporte_handles_executor_exception():
    """If run_in_executor raises, bot sends error message instead of crashing."""
    update = make_update()
    ctx = make_ctx(args=["STK_US"])

    mock_loop = MagicMock()
    mock_loop.run_in_executor = AsyncMock(side_effect=RuntimeError("pipeline exploded"))

    with patch("app.notifications.telegram_bot.TELEGRAM_CHAT_ID", OWNER_ID), \
         patch("app.notifications.telegram_bot._get_operable_market_keys", return_value=["STK_US"]), \
         patch("asyncio.get_event_loop", return_value=mock_loop), \
         patch("app.container.get_container", MagicMock()):
        await cmd_reporte(update, ctx)

    assert update.message.reply_text.call_count == 2
    error_text = update.message.reply_text.call_args_list[1][0][0].lower()
    assert "error" in error_text


# ---------------------------------------------------------------------------
# _MARKET_LABELS and _MARKET_SCHEDULE sanity
# ---------------------------------------------------------------------------

def test_all_schedule_keys_have_labels():
    for key in _MARKET_SCHEDULE:
        assert key in _MARKET_LABELS, f"{key} in _MARKET_SCHEDULE but missing from _MARKET_LABELS"


def test_market_labels_not_empty():
    for key, label in _MARKET_LABELS.items():
        assert label, f"Empty label for market key {key}"
