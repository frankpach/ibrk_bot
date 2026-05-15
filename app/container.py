# app/container.py
"""Dependency injection container."""
from functools import lru_cache

from app.application.ports.broker_port import IBrokerPort
from app.application.ports.notification_port import INotificationPort
from app.application.services.risk_service import RiskService
from app.application.services.position_service import PositionService
from app.application.use_cases.place_order import PlaceOrderUseCase
from app.application.use_cases.close_position import ClosePositionUseCase
from app.infrastructure.broker.ibkr_adapter import IBKRBrokerAdapter
from app.infrastructure.notifications.telegram_adapter import TelegramNotificationAdapter
from app.application.event_bus import EventBus
from app.infrastructure.system.persisted_state import AuditLogHandler
from app.infrastructure.system.secret_manager import SecretManager
from app.infrastructure.db.engine import get_engine, reset_engine
from app.domain.trading.events import (
    CircuitBreakerTriggered,
    ControlSettingChanged,
    OrderPlaced,
    PositionClosed,
    SystemPaused,
    SystemResumed,
    TradingModeSwitched,
)


class Container:
    def __init__(
        self,
        broker: IBrokerPort = None,
        notifier: INotificationPort = None,
        event_bus: EventBus = None,
        engine=None,
    ):
        self.broker = broker or IBKRBrokerAdapter()
        self.notifier = notifier or TelegramNotificationAdapter()
        self.event_bus = event_bus or EventBus()
        self.risk_service = RiskService()
        self.position_service = PositionService()
        from app.alerts.manager import AlertManager
        self.alert_manager = AlertManager(broker=self.broker)
        from app.ibkr.dedup import OrderDeduplicator
        self.order_deduplicator = OrderDeduplicator()
        self.secret_manager = self._init_secret_manager()
        self.engine = engine or get_engine()
        self.place_order_use_case = PlaceOrderUseCase(
            broker=self.broker, notifier=self.notifier, risk_service=self.risk_service,
        )
        self.close_position_use_case = ClosePositionUseCase(
            broker=self.broker, notifier=self.notifier,
        )
        self._register_event_handlers()

    def _init_secret_manager(self) -> SecretManager | None:
        try:
            return SecretManager()
        except RuntimeError:
            return None

    def _register_event_handlers(self) -> None:
        """Wire domain events to their handlers."""
        audit_handler = AuditLogHandler()

        # Audit log handler for all relevant events
        self.event_bus.subscribe(TradingModeSwitched, audit_handler.handle)
        self.event_bus.subscribe(SystemPaused, audit_handler.handle)
        self.event_bus.subscribe(SystemResumed, audit_handler.handle)
        self.event_bus.subscribe(ControlSettingChanged, audit_handler.handle)
        self.event_bus.subscribe(PositionClosed, audit_handler.handle)
        self.event_bus.subscribe(OrderPlaced, audit_handler.handle)
        self.event_bus.subscribe(CircuitBreakerTriggered, audit_handler.handle)

        # Telegram notifications
        self.event_bus.subscribe(TradingModeSwitched, self._on_trading_mode_switched)
        self.event_bus.subscribe(SystemPaused, self._on_system_paused)
        self.event_bus.subscribe(SystemResumed, self._on_system_resumed)
        self.event_bus.subscribe(CircuitBreakerTriggered, self._on_circuit_breaker)
        self.event_bus.subscribe(PositionClosed, self._on_position_closed)

    def _on_trading_mode_switched(self, event: TradingModeSwitched) -> None:
        self.notifier.notify(
            f"Modo cambiado: {event.old_mode} → {event.new_mode} "
            f"(por {event.changed_by})"
        )

    def _on_system_paused(self, event: SystemPaused) -> None:
        self.notifier.notify("Sistema pausado.")

    def _on_system_resumed(self, event: SystemResumed) -> None:
        self.notifier.notify("Sistema reanudado.")

    def _on_circuit_breaker(self, event: CircuitBreakerTriggered) -> None:
        self.notifier.notify(
            f"CIRCUIT BREAKER: perdida {event.loss_pct:.1%} (${event.daily_pnl:.2f})"
        )

    def _on_position_closed(self, event: PositionClosed) -> None:
        self.notifier.notify(
            f"Posicion cerrada: {event.symbol} "
            f"P&L: {event.pnl_pct:.2%} (${event.pnl_usd:.2f})"
        )


@lru_cache(maxsize=1)
def get_container() -> Container:
    return Container()


def test_container() -> Container:
    """Return a container with all mock adapters for testing."""
    from tests.mocks.mock_broker import MockBrokerAdapter
    from tests.mocks.mock_notifications import MockNotificationAdapter
    reset_engine()
    engine = get_engine("sqlite:///:memory:")
    return Container(
        broker=MockBrokerAdapter(),
        notifier=MockNotificationAdapter(),
        event_bus=EventBus(),
        engine=engine,
    )
