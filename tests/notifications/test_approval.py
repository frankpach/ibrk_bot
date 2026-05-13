# tests/notifications/test_approval.py
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from app.notifications.approval import ApprovalManager, get_approval_manager


@pytest.fixture(autouse=True)
def _reset_singleton():
    import app.notifications.approval as amod
    old = amod._approval_manager
    amod._approval_manager = None
    yield
    amod._approval_manager = old


def test_register_bot():
    mgr = ApprovalManager()
    bot = MagicMock()
    mgr.register_bot(bot, "123")
    assert mgr.bot is bot
    assert mgr.chat_id == "123"


@pytest.mark.asyncio
async def test_request_approval_no_bot():
    mgr = ApprovalManager()
    result = await mgr.request_approval("AAPL", "BUY", 10, 100.0, 95.0, 110.0, 50.0)
    assert result is False


@pytest.mark.asyncio
async def test_request_approval_timeout():
    bot = MagicMock()
    bot.send_message = AsyncMock(return_value=MagicMock(message_id=42))
    mgr = ApprovalManager(bot=bot, chat_id="123", timeout=0.1)
    result = await mgr.request_approval("AAPL", "BUY", 10, 100.0, 95.0, 110.0, 50.0)
    assert result is False
    bot.send_message.assert_called_once()


@pytest.mark.asyncio
async def test_request_approval_approved():
    bot = MagicMock()
    bot.send_message = AsyncMock(return_value=MagicMock(message_id=42))
    mgr = ApprovalManager(bot=bot, chat_id="123", timeout=10)
    # Simulate immediate approval
    async def approve_later():
        await asyncio.sleep(0.05)
        mgr._pending["AAPL"].approved = True
    task = asyncio.create_task(approve_later())
    result = await mgr.request_approval("AAPL", "BUY", 10, 100.0, 95.0, 110.0, 50.0)
    await task
    assert result is True


@pytest.mark.asyncio
async def test_request_approval_send_failure():
    bot = MagicMock()
    bot.send_message = AsyncMock(side_effect=Exception("fail"))
    mgr = ApprovalManager(bot=bot, chat_id="123", timeout=10)
    result = await mgr.request_approval("AAPL", "BUY", 10, 100.0, 95.0, 110.0, 50.0)
    assert result is False


def _make_callback_update(data):
    update = MagicMock()
    update.callback_query = MagicMock()
    update.callback_query.data = data
    update.callback_query.answer = AsyncMock()
    return update


@pytest.mark.asyncio
async def test_handle_callback_approve():
    bot = MagicMock()
    mgr = ApprovalManager(bot=bot, chat_id="123", timeout=10)
    mgr._pending["AAPL"] = MagicMock(approved=None, message_id=1)
    await mgr.handle_callback(_make_callback_update("approve_AAPL"), None)
    assert mgr._pending["AAPL"].approved is True


@pytest.mark.asyncio
async def test_handle_callback_cancel():
    bot = MagicMock()
    mgr = ApprovalManager(bot=bot, chat_id="123", timeout=10)
    mgr._pending["AAPL"] = MagicMock(approved=None, message_id=1)
    await mgr.handle_callback(_make_callback_update("cancel_AAPL"), None)
    assert mgr._pending["AAPL"].approved is False


@pytest.mark.asyncio
async def test_handle_callback_no_query():
    mgr = ApprovalManager()
    update = MagicMock()
    update.callback_query = None
    await mgr.handle_callback(update, None)  # should not raise


@pytest.mark.asyncio
async def test_handle_callback_no_data():
    mgr = ApprovalManager()
    update = MagicMock()
    update.callback_query = MagicMock()
    update.callback_query.data = ""
    update.callback_query.answer = AsyncMock()
    await mgr.handle_callback(update, None)  # should not raise


@pytest.mark.asyncio
async def test_handle_callback_invalid_parts():
    mgr = ApprovalManager()
    update = MagicMock()
    update.callback_query = MagicMock()
    update.callback_query.data = "invalid"
    update.callback_query.answer = AsyncMock()
    await mgr.handle_callback(update, None)  # should not raise


@pytest.mark.asyncio
async def test_handle_callback_not_pending():
    bot = MagicMock()
    mgr = ApprovalManager(bot=bot, chat_id="123", timeout=10)
    await mgr.handle_callback(_make_callback_update("approve_AAPL"), None)
    bot.edit_message_text.assert_not_called()


def test_get_pending():
    mgr = ApprovalManager()
    mgr._pending["AAPL"] = MagicMock()
    assert "AAPL" in mgr.get_pending()


def test_get_approval_manager_singleton():
    m1 = get_approval_manager()
    m2 = get_approval_manager()
    assert m1 is m2
