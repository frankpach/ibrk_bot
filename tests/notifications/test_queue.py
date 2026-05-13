# tests/notifications/test_queue.py
import time
from unittest.mock import MagicMock, patch
from app.notifications.queue import NotificationQueue, get_notification_queue, enqueue_notification, _queue_instance


def test_queue_start_stop():
    q = NotificationQueue()
    q.start()
    assert q._thread is not None
    q.stop()
    assert not q._thread.is_alive()


def test_enqueue_drops_when_stopped():
    q = NotificationQueue()
    q.stop()
    q.enqueue("test")  # should not raise


def test_enqueue_puts_message():
    q = NotificationQueue()
    q.start()
    q.enqueue("hello")
    time.sleep(0.1)
    q.stop()


def test_send_no_bot():
    q = NotificationQueue(bot=None, chat_id="123")
    q.start()
    q.enqueue("hello")
    time.sleep(0.3)
    q.stop()


@patch("telegram.Bot")
def test_get_notification_queue(mock_bot):
    global _queue_instance
    _queue_instance = None
    with patch("app.config.settings.TELEGRAM_BOT_TOKEN", "token"):
        with patch("app.config.settings.TELEGRAM_CHAT_ID", "123"):
            q = get_notification_queue()
            assert q is not None


@patch("app.notifications.queue.get_notification_queue")
def test_enqueue_notification(mock_get_q):
    mock_q = MagicMock()
    mock_get_q.return_value = mock_q
    enqueue_notification("hello")
    mock_q.enqueue.assert_called_once_with("hello")


def test_send_with_bot():
    bot = MagicMock()
    q = NotificationQueue(bot=bot, chat_id="123")
    q.start()
    q.enqueue("hello")
    time.sleep(0.3)
    q.stop()


def test_send_retry_once():
    from telegram.error import RetryAfter
    bot = MagicMock()
    bot.send_message.side_effect = [RetryAfter(1), MagicMock()]
    q = NotificationQueue(bot=bot, chat_id="123")
    q.start()
    q.enqueue("hello")
    time.sleep(0.8)
    q.stop()


def test_send_telegram_error():
    from telegram.error import TelegramError
    bot = MagicMock()
    bot.send_message.side_effect = TelegramError("fail")
    q = NotificationQueue(bot=bot, chat_id="123")
    q.start()
    q.enqueue("hello")
    time.sleep(0.3)
    q.stop()


def test_send_generic_error():
    bot = MagicMock()
    bot.send_message.side_effect = Exception("fail")
    q = NotificationQueue(bot=bot, chat_id="123")
    q.start()
    q.enqueue("hello")
    time.sleep(0.3)
    q.stop()
