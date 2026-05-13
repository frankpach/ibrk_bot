# app/notifications/throttler.py
"""NotificationThrottler — deduplicates notifications by message type and content hash."""
import logging
import threading
import time
from typing import Optional

logger = logging.getLogger(__name__)


class NotificationThrottler:
    """
    In-memory throttle for Telegram notifications.
    Prevents re-notifying about conditions already communicated.
    """

    # Throttle rules: key=message_type, value=dict of rules
    THROTTLE_RULES = {
        "circuit_breaker": {"once_per_activation": True, "min_interval_sec": 86400},
        "position_closed": {"once_per_content_hash": True, "min_interval_sec": 86400},
        "position_opened": {"once_per_content_hash": True, "min_interval_sec": 86400},
        "ib_disconnected": {"once_per_event": True, "min_interval_sec": 900},
        "ib_reconnected": {"once_per_event": True, "min_interval_sec": 900},
        "scan_failed": {"once_per_content_hash": True, "min_interval_sec": 3600},
        "signal_ignored": {"min_interval_sec": 300},
        "digest": {"no_throttle": True},
        "generic": {"min_interval_sec": 0},  # default: no throttle
    }

    def __init__(self):
        self._state: dict = {}  # (message_type, content_hash) -> last_sent_at
        self._lock = threading.Lock()

    def notify_if_changed(
        self,
        message_type: str,
        content: str,
        content_hash: Optional[str] = None,
        force: bool = False,
    ) -> bool:
        """
        Returns True if notification should be sent, False if throttled.
        """
        if force:
            return True

        rules = self.THROTTLE_RULES.get(message_type, self.THROTTLE_RULES["generic"])
        if rules.get("no_throttle"):
            return True

        # For once_per_activation/once_per_event: key is just message_type
        # For others: include content_hash for granularity
        if rules.get("once_per_activation") or rules.get("once_per_event"):
            key = (message_type, "")
        else:
            key = (message_type, content_hash or content[:80])
        now = time.time()

        with self._lock:
            last_sent = self._state.get(key)

            if rules.get("once_per_activation") or rules.get("once_per_event"):
                if last_sent is not None:
                    logger.debug(f"Throttled '{message_type}': already sent")
                    return False

            if rules.get("once_per_content_hash"):
                if last_sent is not None:
                    return False

            min_interval = rules.get("min_interval_sec", 0)
            if last_sent is not None and (now - last_sent) < min_interval:
                logger.debug(f"Throttled '{message_type}': sent {(now - last_sent):.0f}s ago")
                return False

            self._state[key] = now
            return True

    def reset_state(self, message_type: str) -> None:
        """Reset throttle state for a message type (e.g. after circuit breaker reset)."""
        with self._lock:
            keys_to_remove = [k for k in self._state if k[0] == message_type]
            for k in keys_to_remove:
                del self._state[k]

    def clear_all(self) -> None:
        """Clear all throttle state."""
        with self._lock:
            self._state.clear()


# Singleton instance
_throttler_instance: Optional[NotificationThrottler] = None


def get_throttler() -> NotificationThrottler:
    global _throttler_instance
    if _throttler_instance is None:
        _throttler_instance = NotificationThrottler()
    return _throttler_instance
