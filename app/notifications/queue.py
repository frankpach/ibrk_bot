# app/notifications/queue.py
"""NotificationQueue — async-safe notification delivery via dedicated thread."""
import logging
import queue
import threading
import time
from typing import Optional

logger = logging.getLogger(__name__)


class NotificationQueue:
    """
    Dedicated daemon thread for Telegram notifications.
    Eliminates asyncio.run() crashes from APScheduler threads.
    """

    def __init__(self, bot=None, chat_id: Optional[str] = None):
        self._bot = bot
        self._chat_id = chat_id
        self._queue: queue.Queue = queue.Queue()
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        logger.info("NotificationQueue started")

    def stop(self) -> None:
        self._stop_event.set()
        self._queue.put(None)  # Wake up thread
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("NotificationQueue stopped")

    def enqueue(self, content: str) -> None:
        if self._stop_event.is_set():
            logger.warning("Queue stopped, dropping message")
            return
        self._queue.put(content)

    def _run(self):
        """Main loop: own the asyncio event loop for telegram bot."""
        import asyncio
        from telegram.error import TelegramError, RetryAfter

        # Create event loop for this thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        # Lazy-init bot if not provided
        bot = self._bot
        if bot is None:
            from app.config.settings import TELEGRAM_BOT_TOKEN
            from telegram import Bot
            if TELEGRAM_BOT_TOKEN:
                bot = Bot(token=TELEGRAM_BOT_TOKEN)

        while not self._stop_event.is_set():
            try:
                content = self._queue.get(timeout=1)
            except queue.Empty:
                continue
            if content is None:
                break
            self._send(bot, loop, content)

        loop.close()

    def _send(self, bot, loop, content: str):
        """Send a single notification with retry logic."""
        if bot is None or self._chat_id is None:
            logger.warning("Telegram not configured, logging notification: %s", content[:80])
            return

        import asyncio
        from telegram.error import TelegramError, RetryAfter

        async def _do_send():
            try:
                await bot.send_message(
                    chat_id=self._chat_id,
                    text=content,
                    parse_mode="HTML",
                )
                logger.info("Notification sent: %s", content[:80])
                return True
            except RetryAfter as e:
                logger.warning("Telegram rate limit, retry after %s", e.retry_after)
                await asyncio.sleep(min(e.retry_after, 30))
                return False  # Will be retried by outer loop
            except TelegramError as e:
                logger.error("Telegram error: %s", e)
                return True  # Don't retry Telegram errors
            except Exception as e:
                logger.error("Send failed: %s", e)
                return True  # Don't retry unknown errors

        # Try once, retry once after 5s on rate limit
        for attempt in range(2):
            done = asyncio.run_coroutine_threadsafe(_do_send(), loop).result(timeout=30)
            if done:
                break
            if attempt == 0:
                time.sleep(5)
            else:
                logger.error("Notification failed after retry: %s", content[:80])


# Singleton
_queue_instance: Optional[NotificationQueue] = None


def get_notification_queue() -> NotificationQueue:
    global _queue_instance
    if _queue_instance is None:
        from app.config.settings import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
        from telegram import Bot
        bot = Bot(token=TELEGRAM_BOT_TOKEN) if TELEGRAM_BOT_TOKEN else None
        _queue_instance = NotificationQueue(bot=bot, chat_id=TELEGRAM_CHAT_ID)
    return _queue_instance


def enqueue_notification(content: str) -> None:
    """Convenience function to enqueue a notification."""
    get_notification_queue().enqueue(content)
