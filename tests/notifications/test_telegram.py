# tests/notifications/test_telegram.py
from unittest.mock import MagicMock, patch
from app.notifications.telegram import notify, request_approval


def test_notify_when_not_configured():
    with patch("app.notifications.telegram.TELEGRAM_BOT_TOKEN", None):
        assert notify("hello") is False


def test_notify_suppressed_by_policy():
    with patch("app.notifications.telegram._get_bot") as mock_get_bot:
        mock_policy = MagicMock()
        mock_policy.should_notify.return_value = False
        with patch("app.notifications.policy.get_policy", return_value=mock_policy):
            assert notify("hello", "position_opened") is False
        mock_get_bot.assert_not_called()


def test_notify_success():
    with patch("app.notifications.telegram._get_bot") as mock_get_bot:
        mock_bot = MagicMock()
        mock_get_bot.return_value = mock_bot
        mock_policy = MagicMock()
        mock_policy.should_notify.return_value = True
        with patch("app.notifications.policy.get_policy", return_value=mock_policy):
            with patch("asyncio.run") as mock_asyncio:
                assert notify("hello", "circuit_breaker") is True
                mock_asyncio.assert_called_once()


def test_notify_failure():
    with patch("app.notifications.telegram._get_bot") as mock_get_bot:
        mock_bot = MagicMock()
        mock_get_bot.return_value = mock_bot
        mock_policy = MagicMock()
        mock_policy.should_notify.return_value = True
        with patch("app.notifications.policy.get_policy", return_value=mock_policy):
            with patch("asyncio.run", side_effect=Exception("fail")):
                assert notify("hello") is False


def test_request_approval_not_configured():
    with patch("app.notifications.telegram.TELEGRAM_BOT_TOKEN", None):
        assert request_approval("AAPL", "BUY", 10, 100.0, 98.0, 110.0, 50.0) is False


def test_request_approval_timeout():
    with patch("app.notifications.telegram._get_bot") as mock_get_bot, \
         patch("app.notifications.telegram.TELEGRAM_APPROVAL_TIMEOUT_SECONDS", 0):
        mock_bot = MagicMock()
        mock_get_bot.return_value = mock_bot
        with patch("asyncio.run") as mock_asyncio:
            # First call sends message, second call checks updates (empty)
            mock_asyncio.side_effect = [MagicMock(message_id=1), False]
            result = request_approval("AAPL", "BUY", 10, 100.0, 98.0, 110.0, 50.0)
            assert result is False


def test_request_approval_exception():
    with patch("app.notifications.telegram._get_bot") as mock_get_bot:
        mock_bot = MagicMock()
        mock_get_bot.return_value = mock_bot
        with patch("asyncio.run", side_effect=Exception("send fail")):
            result = request_approval("AAPL", "BUY", 10, 100.0, 98.0, 110.0, 50.0)
            assert result is False
