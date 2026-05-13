# tests/notifications/test_telegram_bot.py
import json
import asyncio
import pytest
from unittest.mock import MagicMock, patch
from telegram import Update
from telegram.ext import ContextTypes

from app.notifications.telegram_bot import (
    _api, _call_opencode, _only_owner,
    cmd_estado, cmd_posiciones, cmd_cerrar,
    cmd_analizar, cmd_ayuda, cmd_diagnostico,
    cmd_modo,
)


def test_api_success():
    with patch("app.notifications.telegram_bot.httpx.get") as mock_get:
        mock_get.return_value = MagicMock(json=lambda: {"status": "ok"})
        result = _api("get", "/health")
        assert result["status"] == "ok"


def test_api_error():
    with patch("app.notifications.telegram_bot.httpx.get", side_effect=Exception("fail")):
        result = _api("get", "/health")
        assert "error" in result


@patch("app.notifications.telegram_bot.subprocess.run")
def test_call_opencode_success(mock_run):
    mock_run.return_value = MagicMock(
        stdout=json.dumps({"type": "text", "part": {"text": "hello"}}),
        stderr="",
    )
    result = _call_opencode("prompt")
    assert result == "hello"


@patch("app.notifications.telegram_bot.subprocess.run", side_effect=Exception("fail"))
def test_call_opencode_error(mock_run):
    result = _call_opencode("prompt")
    assert "Error" in result


@pytest.mark.asyncio
async def test_only_owner_blocks():
    async def dummy(update, ctx):
        return "called"
    wrapped = _only_owner(dummy)
    update = MagicMock()
    update.effective_chat.id = 999
    with patch("app.notifications.telegram_bot.TELEGRAM_CHAT_ID", "123"):
        result = await wrapped(update, None)
    assert result is None


@pytest.mark.asyncio
async def test_only_owner_allows():
    async def dummy(update, ctx):
        return "called"
    wrapped = _only_owner(dummy)
    update = MagicMock()
    update.effective_chat.id = 123
    with patch("app.notifications.telegram_bot.TELEGRAM_CHAT_ID", "123"):
        result = await wrapped(update, None)
    assert result == "called"


@pytest.mark.asyncio
async def test_cmd_estado():
    update = MagicMock()
    update.effective_chat.id = 123
    update.message.reply_text = AsyncMock()
    ctx = MagicMock()
    with patch("app.notifications.telegram_bot._api") as mock_api, \
         patch("app.notifications.telegram_bot.TELEGRAM_CHAT_ID", "123"):
        mock_api.side_effect = [
            {"paused": False, "mode": "paper", "open_positions": 0, "daily_pnl_usd": 0, "operating_capital": 1000, "ib_connected": True},
            [],
            {"net_liquidation": 1000},
        ]
        await cmd_estado(update, ctx)
        update.message.reply_text.assert_called_once()


@pytest.mark.asyncio
async def test_cmd_posiciones():
    update = MagicMock()
    update.effective_chat.id = 123
    update.message.reply_text = AsyncMock()
    ctx = MagicMock()
    with patch("app.notifications.telegram_bot._api", return_value=[{"symbol": "AAPL", "quantity": 10, "avg_cost": 100, "market_value": 1000, "unrealized_pnl": 50, "stop_loss_price": 98.0, "take_profit_price": 110.0}]), \
         patch("app.notifications.telegram_bot.TELEGRAM_CHAT_ID", "123"):
        await cmd_posiciones(update, ctx)
        update.message.reply_text.assert_called_once()


@pytest.mark.asyncio
async def test_cmd_cerrar_no_args():
    update = MagicMock()
    update.effective_chat.id = 123
    update.message.reply_text = AsyncMock()
    ctx = MagicMock()
    ctx.args = []
    with patch("app.notifications.telegram_bot.TELEGRAM_CHAT_ID", "123"):
        await cmd_cerrar(update, ctx)
        update.message.reply_text.assert_called_once()
        assert "uso" in update.message.reply_text.call_args[0][0].lower()


@pytest.mark.asyncio
async def test_cmd_cerrar_todo():
    update = MagicMock()
    update.effective_chat.id = 123
    update.message.reply_text = AsyncMock()
    ctx = MagicMock()
    ctx.args = ["todo"]
    with patch("app.notifications.telegram_bot._api", return_value={"closed": 2}), \
         patch("app.notifications.telegram_bot.TELEGRAM_CHAT_ID", "123"):
        await cmd_cerrar(update, ctx)
        update.message.reply_text.assert_called_once()


@pytest.mark.asyncio
async def test_cmd_cerrar_symbol():
    update = MagicMock()
    update.effective_chat.id = 123
    update.message.reply_text = AsyncMock()
    ctx = MagicMock()
    ctx.args = ["aapl"]
    with patch("app.notifications.telegram_bot._api", return_value={"exit_price": 105.0, "pnl_usd": 50.0, "pnl_pct": 0.05}), \
         patch("app.notifications.telegram_bot.TELEGRAM_CHAT_ID", "123"):
        await cmd_cerrar(update, ctx)
        update.message.reply_text.assert_called_once()


@pytest.mark.asyncio
async def test_cmd_analizar():
    update = MagicMock()
    update.effective_chat.id = 123
    update.message.reply_text = AsyncMock()
    ctx = MagicMock()
    ctx.args = ["AAPL"]
    mock_result = MagicMock()
    mock_result.score = MagicMock(total=75, momentum=0.7, trend=0.6, volume=0.5, volatility=0.4, portfolio_fit=0.8, sentiment=0.3, price_change=0.2)
    mock_result.recommendation = "BUY"
    mock_result.llm_confidence = 0.8
    mock_result.llm_narrative = "Bullish"
    mock_result.hard_rules = MagicMock(passed=True, warnings=[])
    mock_result.in_universe = True
    mock_result.failed_at_step = None
    future = asyncio.Future()
    future.set_result(mock_result)
    mock_loop = MagicMock()
    mock_loop.run_in_executor.return_value = future
    with patch("app.notifications.telegram_bot.TELEGRAM_CHAT_ID", "123"), \
         patch("asyncio.get_event_loop", return_value=mock_loop):
        await cmd_analizar(update, ctx)
        assert update.message.reply_text.call_count == 2


@pytest.mark.asyncio
async def test_cmd_analizar_no_args():
    update = MagicMock()
    update.effective_chat.id = 123
    update.message.reply_text = AsyncMock()
    ctx = MagicMock()
    ctx.args = []
    with patch("app.notifications.telegram_bot.TELEGRAM_CHAT_ID", "123"):
        await cmd_analizar(update, ctx)
        update.message.reply_text.assert_called_once()


@pytest.mark.asyncio
async def test_cmd_ayuda():
    update = MagicMock()
    update.effective_chat.id = 123
    update.message.reply_text = AsyncMock()
    ctx = MagicMock()
    with patch("app.notifications.telegram_bot.TELEGRAM_CHAT_ID", "123"):
        await cmd_ayuda(update, ctx)
        update.message.reply_text.assert_called_once()


@pytest.mark.asyncio
async def test_cmd_diagnostico():
    update = MagicMock()
    update.effective_chat.id = 123
    update.message.reply_text = AsyncMock()
    ctx = MagicMock()
    with patch("app.notifications.telegram_bot._api") as mock_api, \
         patch("app.notifications.telegram_bot.TELEGRAM_CHAT_ID", "123"):
        mock_api.return_value = {"available": [{"label": "Stocks"}], "unavailable": []}
        await cmd_diagnostico(update, ctx)
        update.message.reply_text.assert_called_once()


@pytest.mark.asyncio
async def test_cmd_modo_invalid():
    update = MagicMock()
    update.effective_chat.id = 123
    update.message.reply_text = AsyncMock()
    ctx = MagicMock()
    ctx.args = []
    with patch("app.notifications.telegram_bot.TELEGRAM_CHAT_ID", "123"):
        await cmd_modo(update, ctx)
        update.message.reply_text.assert_called_once()
        assert "uso" in update.message.reply_text.call_args[0][0].lower()


class AsyncMock(MagicMock):
    async def __call__(self, *args, **kwargs):
        return super(AsyncMock, self).__call__(*args, **kwargs)
