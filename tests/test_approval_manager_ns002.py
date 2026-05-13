import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock
from app.notifications.approval import ApprovalManager, PendingApproval


class TestApprovalManager:
    def test_pending_approval_dataclass(self):
        p = PendingApproval(
            symbol="NVDA", action="BUY", units=1.0,
            entry_price=214.91, stop_loss_price=209.54,
            take_profit_price=227.8, estimated_risk_usd=5.37,
            deadline=1234567890,
        )
        assert p.symbol == "NVDA"
        assert p.approved is None

    @pytest.mark.asyncio
    async def test_request_approval_timeout(self):
        manager = ApprovalManager(timeout=0.1)
        mock_bot = MagicMock()
        mock_bot.send_message = AsyncMock(return_value=MagicMock(message_id=42))
        mock_bot.edit_message_text = AsyncMock()
        manager.register_bot(mock_bot, "12345")

        result = await manager.request_approval(
            symbol="NVDA", action="BUY", units=1.0,
            entry_price=214.91, stop_loss_price=209.54,
            take_profit_price=227.8, estimated_risk_usd=5.37,
        )
        assert result is False  # Timeout

    @pytest.mark.asyncio
    async def test_handle_callback_approve(self):
        manager = ApprovalManager()
        # Create a pending approval manually
        manager._pending["AAPL"] = PendingApproval(
            symbol="AAPL", action="BUY", units=1.0,
            entry_price=100.0, stop_loss_price=97.5,
            take_profit_price=106.0, estimated_risk_usd=2.5,
            deadline=9999999999,
        )

        mock_update = MagicMock()
        mock_update.callback_query = MagicMock()
        mock_update.callback_query.data = "approve_AAPL"
        mock_update.callback_query.answer = AsyncMock()

        await manager.handle_callback(mock_update, None)
        assert manager._pending["AAPL"].approved is True

    @pytest.mark.asyncio
    async def test_handle_callback_cancel(self):
        manager = ApprovalManager()
        manager._pending["TSLA"] = PendingApproval(
            symbol="TSLA", action="SELL", units=0.5,
            entry_price=250.0, stop_loss_price=256.25,
            take_profit_price=235.0, estimated_risk_usd=3.12,
            deadline=9999999999,
        )

        mock_update = MagicMock()
        mock_update.callback_query = MagicMock()
        mock_update.callback_query.data = "cancel_TSLA"
        mock_update.callback_query.answer = AsyncMock()

        await manager.handle_callback(mock_update, None)
        assert manager._pending["TSLA"].approved is False

    @pytest.mark.asyncio
    async def test_handle_callback_unknown_symbol(self):
        manager = ApprovalManager()
        mock_update = MagicMock()
        mock_update.callback_query = MagicMock()
        mock_update.callback_query.data = "approve_UNKNOWN"
        mock_update.callback_query.answer = AsyncMock()

        await manager.handle_callback(mock_update, None)
        # Should not crash, just ignore
        assert "UNKNOWN" not in manager._pending

    def test_get_pending_empty(self):
        manager = ApprovalManager()
        assert manager.get_pending() == {}

    def test_get_pending_with_items(self):
        manager = ApprovalManager()
        manager._pending["NVDA"] = PendingApproval(
            symbol="NVDA", action="BUY", units=1.0,
            entry_price=214.91, stop_loss_price=209.54,
            take_profit_price=227.8, estimated_risk_usd=5.37,
            deadline=1234567890,
        )
        pending = manager.get_pending()
        assert len(pending) == 1
        assert "NVDA" in pending
