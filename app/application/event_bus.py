# app/application/event_bus.py
"""In-process synchronous event bus."""
from __future__ import annotations

import structlog
from typing import Callable

from app.domain.trading.events import DomainEvent

logger = structlog.get_logger(__name__)


class EventBus:
    """
    In-process, synchronous event bus.
    A handler that raises an exception does NOT interrupt publication to other handlers.
    Errors in handlers are logged but not propagated to the publisher.
    """

    def __init__(self):
        self._handlers: dict[type, list[Callable]] = {}

    def subscribe(self, event_type: type, handler: Callable) -> None:
        """Register a handler for a specific event type."""
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)

    def publish(self, event: DomainEvent) -> None:
        """Publish an event to all registered handlers for its type."""
        event_type = type(event)
        handlers = self._handlers.get(event_type, [])
        for handler in handlers:
            try:
                handler(event)
            except Exception as exc:
                logger.error("handler_failed", handler=handler.__name__, error=str(exc))
