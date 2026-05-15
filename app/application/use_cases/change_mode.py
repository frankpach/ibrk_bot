# app/application/use_cases/change_mode.py
"""ChangeTradingModeUseCase — validates, persists, reconnects, publishes event."""
from dataclasses import dataclass

import structlog

from app.application.event_bus import EventBus
from app.application.ports.broker_port import IBrokerPort
from app.application.ports.notification_port import INotificationPort
from app.infrastructure.db.compat import get_control_settings, update_control_setting, get_trades_by_status
from app.domain.trading.events import TradingModeSwitched

logger = structlog.get_logger(__name__)


@dataclass
class ChangeModeResult:
    success: bool
    warning: str | None = None
    error: str | None = None


class ChangeTradingModeUseCase:
    def __init__(
        self,
        scheduler,
        broker: IBrokerPort,
        notifier: INotificationPort,
        event_bus: EventBus,
        changed_by: str = "system",
    ):
        self._scheduler = scheduler
        self._broker = broker
        self._notifier = notifier
        self._event_bus = event_bus
        self._changed_by = changed_by

    def execute(self, mode: str) -> ChangeModeResult:
        if mode not in ("paper", "live"):
            raise ValueError(f"Invalid mode: {mode}")

        # Validate no orders in flight (SUBMITTED)
        submitted = get_trades_by_status("SUBMITTED")
        if submitted:
            warning = (
                f"Hay {len(submitted)} orden(es) en vuelo (status=SUBMITTED). "
                f"Espera a que se completen antes de cambiar el modo."
            )
            return ChangeModeResult(success=False, warning=warning)

        # Check for open positions
        open_positions = get_trades_by_status("OPEN")
        if open_positions:
            warning = (
                f"Hay {len(open_positions)} posicion(es) abierta(s). "
                f"Confirma si deseas continuar cambiando el modo."
            )
            # The caller decides whether to confirm; for now return warning
            # If this is the first call without confirmation, we block
            # In a real UI flow, the caller would pass `confirmed=True` on retry
            return ChangeModeResult(success=False, warning=warning)

        old_mode = get_control_settings().get("trading_mode", "paper")

        # Persist mode
        update_control_setting("trading_mode", mode)

        # Persist IB port based on mode
        ib_port = 4002 if mode == "paper" else 4001
        update_control_setting("ib_port", str(ib_port))

        # Reconnect IB automatically
        try:
            self._broker.reconnect(port=ib_port)
        except Exception as exc:
            logger.warning(f"IB reconnect failed during mode change: {exc}")

        # Publish event
        self._event_bus.publish(
            TradingModeSwitched(old_mode=old_mode, new_mode=mode, changed_by=self._changed_by)
        )

        logger.info(f"Trading mode changed from {old_mode} to {mode}")
        return ChangeModeResult(success=True)
