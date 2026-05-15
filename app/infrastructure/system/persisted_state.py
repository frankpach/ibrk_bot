# app/infrastructure/system/persisted_state.py
"""Persisted state handlers: AuditLogHandler writes to the audit_log table."""
from datetime import datetime, timezone

import structlog

from app.infrastructure.db.compat import get_connection
from app.domain.trading.events import (
    CircuitBreakerTriggered,
    ControlSettingChanged,
    DomainEvent,
    OrderPlaced,
    PositionClosed,
    SystemPaused,
    SystemResumed,
    TradingModeSwitched,
)

logger = structlog.get_logger(__name__)


class AuditLogHandler:
    """
    Handler that persists domain events to the audit_log table.
    The audit_log is append-only: no UPDATE or DELETE operations.
    Fields with is_secret=True are recorded as '[SECRET_UPDATED]'.
    """

    def handle(self, event: DomainEvent) -> None:
        try:
            self._insert(event)
        except Exception as exc:
            logger.error("audit_log_insert_failed", error=str(exc))

    def _insert(self, event: DomainEvent) -> None:
        if isinstance(event, TradingModeSwitched):
            self._write(
                event_type="mode_changed",
                entity_type="system",
                old_value=event.old_mode,
                new_value=event.new_mode,
                changed_by=event.changed_by,
            )
        elif isinstance(event, SystemPaused):
            self._write(
                event_type="system_paused",
                entity_type="system",
                old_value="running",
                new_value="paused",
            )
        elif isinstance(event, SystemResumed):
            self._write(
                event_type="system_resumed",
                entity_type="system",
                old_value="paused",
                new_value="running",
            )
        elif isinstance(event, ControlSettingChanged):
            old_val = "[SECRET_UPDATED]" if event.is_secret else event.old_value
            new_val = "[SECRET_UPDATED]" if event.is_secret else event.new_value
            self._write(
                event_type="control_setting_changed",
                entity_type="setting",
                entity_id=None,
                old_value=old_val,
                new_value=new_val,
                changed_by=event.changed_by,
            )
        elif isinstance(event, PositionClosed):
            self._write(
                event_type="position_closed",
                entity_type="trade",
                entity_id=event.trade_id,
                old_value=None,
                new_value=f"pnl_usd={event.pnl_usd:.2f}",
            )
        elif isinstance(event, OrderPlaced):
            self._write(
                event_type="order_placed",
                entity_type="trade",
                entity_id=event.trade_id,
                old_value=None,
                new_value=f"{event.action} {event.quantity} {event.symbol}",
            )
        elif isinstance(event, CircuitBreakerTriggered):
            self._write(
                event_type="circuit_breaker_triggered",
                entity_type="system",
                old_value=None,
                new_value=f"loss_pct={event.loss_pct:.4f}",
            )

    def _write(
        self,
        event_type: str,
        entity_type: str | None = None,
        entity_id: int | None = None,
        old_value: str | None = None,
        new_value: str | None = None,
        changed_by: str | None = None,
        ip_address: str | None = None,
    ) -> None:
        conn = get_connection()
        try:
            conn.execute(
                """INSERT INTO audit_log
                   (event_type, entity_type, entity_id, old_value, new_value, changed_by, ip_address, occurred_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    event_type,
                    entity_type,
                    entity_id,
                    old_value,
                    new_value,
                    changed_by,
                    ip_address,
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
            conn.commit()
        finally:
            conn.close()
