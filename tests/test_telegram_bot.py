# tests/test_telegram_bot.py
from unittest.mock import AsyncMock, MagicMock, patch
import pytest


def make_update(chat_id="8645527459"):
    update = MagicMock()
    update.effective_chat.id = chat_id
    update.message.text = "test"
    update.message.reply_text = AsyncMock()
    return update


@pytest.mark.asyncio
async def test_estado_calls_system_status():
    with patch("app.notifications.telegram_bot._api") as mock_api, \
         patch("app.notifications.telegram_bot.TELEGRAM_CHAT_ID", "8645527459"):
        mock_api.side_effect = [
            {"mode": "paper", "paused": False, "simulated_capital": 500,
             "daily_pnl_usd": 0.0, "daily_pnl_pct": 0.0, "open_positions": 0},
            [],
            {"net_liquidation": 1000.0},
        ]
        from app.notifications.telegram_bot import cmd_estado
        update = make_update()
        await cmd_estado(update, MagicMock())
        update.message.reply_text.assert_called_once()
        text = update.message.reply_text.call_args[0][0]
        assert "paper" in text.lower()


@pytest.mark.asyncio
async def test_cerrar_sin_args_muestra_uso():
    with patch("app.notifications.telegram_bot.TELEGRAM_CHAT_ID", "8645527459"):
        from app.notifications.telegram_bot import cmd_cerrar
        update = make_update()
        ctx = MagicMock()
        ctx.args = []
        await cmd_cerrar(update, ctx)
        text = update.message.reply_text.call_args[0][0]
        assert "Uso" in text


@pytest.mark.asyncio
async def test_modo_live_pide_confirmacion():
    with patch("app.notifications.telegram_bot.TELEGRAM_CHAT_ID", "8645527459"):
        from app.notifications.telegram_bot import cmd_modo
        update = make_update()
        ctx = MagicMock()
        ctx.args = ["live"]
        await cmd_modo(update, ctx)
        text = update.message.reply_text.call_args[0][0]
        assert "ADVERTENCIA" in text


@pytest.mark.asyncio
async def test_owner_filter_blocks_other_chats():
    with patch("app.notifications.telegram_bot.TELEGRAM_CHAT_ID", "8645527459"):
        from app.notifications.telegram_bot import cmd_estado
        update = make_update(chat_id="999999")
        await cmd_estado(update, MagicMock())
        update.message.reply_text.assert_not_called()


@pytest.mark.asyncio
async def test_ayuda_lists_all_sections():
    with patch("app.notifications.telegram_bot.TELEGRAM_CHAT_ID", "8645527459"):
        from app.notifications.telegram_bot import cmd_ayuda
        update = make_update()
        await cmd_ayuda(update, MagicMock())
        text = update.message.reply_text.call_args[0][0]
        assert "/estado" in text
        assert "/analizar" in text
        assert "/cerrar" in text
