# tests/test_issue004_persist_state.py
"""Tests for Issue 004: Persist System State, Auditoría y Event Bus."""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from unittest.mock import MagicMock

import pytest

from app.application.event_bus import EventBus
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
from app.application.use_cases.change_mode import ChangeTradingModeUseCase
from app.application.use_cases.pause_system import PauseSystemUseCase, ResumeSystemUseCase
from app.infrastructure.notifications.telegram_adapter import TelegramNotificationAdapter
from app.infrastructure.db.compat import get_connection, get_control_settings, update_control_setting


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class FakeScheduler:
    """Mock APScheduler for pause/resume tests."""

    def __init__(self):
        self.jobs: dict[str, dict] = {}
        self._paused: set[str] = set()

    def add_job(self, func, trigger, **kwargs):
        job_id = kwargs.get("id", f"job_{len(self.jobs)}")
        self.jobs[job_id] = {"func": func, "trigger": trigger, "kwargs": kwargs}

    def pause_job(self, job_id: str) -> None:
        if job_id not in self.jobs:
            raise LookupError(f"Job {job_id} not found")
        self._paused.add(job_id)

    def resume_job(self, job_id: str) -> None:
        if job_id not in self.jobs:
            raise LookupError(f"Job {job_id} not found")
        self._paused.discard(job_id)

    def get_job(self, job_id: str):
        if job_id not in self.jobs:
            return None
        return MagicMock(id=job_id)


class FakeBroker:
    def reconnect(self, port: int = 4002) -> None:
        self.last_reconnect_port = port


class FakeNotifier:
    def __init__(self):
        self.messages: list[str] = []
        self.approval_responses: list[dict] = []

    def notify(self, message: str) -> None:
        self.messages.append(message)

    def request_approval(self, **kwargs) -> bool:
        self.approval_responses.append(kwargs)
        return True


class FakeEventBus:
    def __init__(self):
        self.events: list[DomainEvent] = []

    def publish(self, event: DomainEvent) -> None:
        self.events.append(event)


# ---------------------------------------------------------------------------
# EventBus tests
# ---------------------------------------------------------------------------

def test_event_bus_publishes_to_all_handlers():
    bus = EventBus()
    calls: list[str] = []

    def handler_a(event: DomainEvent):
        calls.append("a")

    def handler_b(event: DomainEvent):
        calls.append("b")

    bus.subscribe(TradingModeSwitched, handler_a)
    bus.subscribe(TradingModeSwitched, handler_b)
    bus.publish(TradingModeSwitched(old_mode="paper", new_mode="live"))

    assert calls == ["a", "b"]


def test_event_bus_handler_exception_does_not_stop_others():
    bus = EventBus()
    calls: list[str] = []

    def handler_a(event: DomainEvent):
        calls.append("a")
        raise RuntimeError("boom")

    def handler_b(event: DomainEvent):
        calls.append("b")

    bus.subscribe(TradingModeSwitched, handler_a)
    bus.subscribe(TradingModeSwitched, handler_b)
    bus.publish(TradingModeSwitched(old_mode="paper", new_mode="live"))

    assert "a" in calls
    assert "b" in calls


def test_event_bus_no_handlers_no_error():
    bus = EventBus()
    bus.publish(TradingModeSwitched(old_mode="paper", new_mode="live"))


# ---------------------------------------------------------------------------
# ChangeTradingModeUseCase tests
# ---------------------------------------------------------------------------

def test_change_mode_paper_to_live_persists_and_reconnects():
    scheduler = FakeScheduler()
    broker = FakeBroker()
    notifier = FakeNotifier()
    event_bus = FakeEventBus()

    use_case = ChangeTradingModeUseCase(
        scheduler=scheduler,
        broker=broker,
        notifier=notifier,
        event_bus=event_bus,
        changed_by="admin_key",
    )

    result = use_case.execute("live")

    assert result.success is True
    assert result.warning is None
    settings = get_control_settings()
    assert settings.get("trading_mode") == "live"
    assert broker.last_reconnect_port == 4001
    assert len(event_bus.events) == 1
    assert isinstance(event_bus.events[0], TradingModeSwitched)


def test_change_mode_with_submitted_orders_returns_warning():
    scheduler = FakeScheduler()
    broker = FakeBroker()
    notifier = FakeNotifier()
    event_bus = FakeEventBus()

    # Seed a SUBMITTED trade
    conn = get_connection()
    conn.execute(
        """INSERT INTO trades
           (symbol, action, quantity, entry_price, stop_loss_price, take_profit_price,
            stop_loss_pct, take_profit_pct, signal_strength, status, opened_at,
            trade_status, order_id)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        ("AAPL", "BUY", 10, 150.0, 145.0, 160.0, 0.025, 0.06, "STRONG",
         "OPEN", datetime.now(timezone.utc).isoformat(), "SUBMITTED", "order-123"),
    )
    conn.commit()
    conn.close()

    use_case = ChangeTradingModeUseCase(
        scheduler=scheduler,
        broker=broker,
        notifier=notifier,
        event_bus=event_bus,
        changed_by="admin_key",
    )

    result = use_case.execute("live")

    assert result.success is False
    assert result.warning is not None
    assert "orden" in result.warning.lower() or "order" in result.warning.lower()
    settings = get_control_settings()
    assert settings.get("trading_mode") != "live"


def test_change_mode_creates_audit_log_entry():
    from app.infrastructure.system.persisted_state import AuditLogHandler

    scheduler = FakeScheduler()
    broker = FakeBroker()
    notifier = FakeNotifier()
    event_bus = EventBus()
    event_bus.subscribe(TradingModeSwitched, AuditLogHandler().handle)

    use_case = ChangeTradingModeUseCase(
        scheduler=scheduler,
        broker=broker,
        notifier=notifier,
        event_bus=event_bus,
        changed_by="admin_key",
    )

    use_case.execute("live")

    conn = get_connection()
    row = conn.execute(
        "SELECT event_type, changed_by FROM audit_log WHERE event_type = 'mode_changed' ORDER BY id DESC LIMIT 1"
    ).fetchone()
    conn.close()

    assert row is not None
    assert row["event_type"] == "mode_changed"
    assert row["changed_by"] == "admin_key"


def test_change_mode_invalid_mode_raises():
    use_case = ChangeTradingModeUseCase(
        scheduler=FakeScheduler(),
        broker=FakeBroker(),
        notifier=FakeNotifier(),
        event_bus=FakeEventBus(),
    )
    with pytest.raises(ValueError, match="Invalid mode"):
        use_case.execute("invalid")


# ---------------------------------------------------------------------------
# PauseSystemUseCase tests
# ---------------------------------------------------------------------------

def test_pause_system_pauses_specific_jobs():
    scheduler = FakeScheduler()
    for job_id in ("signal_processor", "scanner", "scanner_fetch", "news_fetch",
                   "position_manager", "circuit_breaker"):
        scheduler.add_job(lambda: None, "interval", minutes=1, id=job_id)

    notifier = FakeNotifier()
    event_bus = FakeEventBus()

    use_case = PauseSystemUseCase(scheduler=scheduler, notifier=notifier, event_bus=event_bus)
    result = use_case.execute()

    assert result.success is True
    assert "signal_processor" in scheduler._paused
    assert "scanner" in scheduler._paused
    assert "scanner_fetch" in scheduler._paused
    assert "news_fetch" in scheduler._paused
    assert "position_manager" not in scheduler._paused
    assert "circuit_breaker" not in scheduler._paused
    assert len(event_bus.events) == 1
    assert isinstance(event_bus.events[0], SystemPaused)


def test_pause_system_persists_state():
    scheduler = FakeScheduler()
    for job_id in ("signal_processor", "scanner"):
        scheduler.add_job(lambda: None, "interval", minutes=1, id=job_id)

    use_case = PauseSystemUseCase(
        scheduler=scheduler, notifier=FakeNotifier(), event_bus=FakeEventBus()
    )
    use_case.execute()

    settings = get_control_settings()
    assert settings.get("is_paused") is True


def test_pause_system_idempotent():
    scheduler = FakeScheduler()
    scheduler.add_job(lambda: None, "interval", minutes=1, id="signal_processor")
    scheduler._paused.add("signal_processor")

    event_bus = FakeEventBus()
    use_case = PauseSystemUseCase(
        scheduler=scheduler, notifier=FakeNotifier(), event_bus=event_bus
    )
    result = use_case.execute()

    assert result.success is True
    assert len(event_bus.events) == 1


def test_resume_system_reverses_pause():
    scheduler = FakeScheduler()
    for job_id in ("signal_processor", "scanner", "scanner_fetch", "news_fetch"):
        scheduler.add_job(lambda: None, "interval", minutes=1, id=job_id)
        scheduler._paused.add(job_id)

    notifier = FakeNotifier()
    event_bus = FakeEventBus()

    use_case = ResumeSystemUseCase(scheduler=scheduler, notifier=notifier, event_bus=event_bus)
    result = use_case.execute()

    assert result.success is True
    assert scheduler._paused == set()
    settings = get_control_settings()
    assert settings.get("is_paused") is False
    assert len(event_bus.events) == 1
    assert isinstance(event_bus.events[0], SystemResumed)


# ---------------------------------------------------------------------------
# TelegramNotificationAdapter tests
# ---------------------------------------------------------------------------

def test_telegram_adapter_implements_port():
    from app.application.ports.notification_port import INotificationPort

    adapter = TelegramNotificationAdapter()
    assert isinstance(adapter, INotificationPort)


def test_telegram_adapter_notify_delegates():
    adapter = TelegramNotificationAdapter()
    # Should not raise even without Telegram configured
    adapter.notify("test message")


def test_telegram_adapter_request_approval_delegates():
    adapter = TelegramNotificationAdapter()
    result = adapter.request_approval(
        symbol="AAPL", action="BUY", units=10,
        entry_price=150.0, stop_loss_price=145.0,
        take_profit_price=160.0, estimated_risk_usd=50.0,
    )
    assert isinstance(result, bool)


# ---------------------------------------------------------------------------
# AuditLogHandler tests
# ---------------------------------------------------------------------------

def test_audit_log_handler_writes_on_trading_mode_switched():
    from app.application.event_bus import EventBus
    from app.infrastructure.system.persisted_state import AuditLogHandler

    bus = EventBus()
    handler = AuditLogHandler()
    bus.subscribe(TradingModeSwitched, handler.handle)

    bus.publish(TradingModeSwitched(old_mode="paper", new_mode="live", changed_by="admin_key"))

    conn = get_connection()
    row = conn.execute(
        "SELECT event_type, old_value, new_value, changed_by FROM audit_log WHERE event_type = 'mode_changed' ORDER BY id DESC LIMIT 1"
    ).fetchone()
    conn.close()

    assert row is not None
    assert row["old_value"] == "paper"
    assert row["new_value"] == "live"
    assert row["changed_by"] == "admin_key"


def test_audit_log_handler_writes_secret_as_masked():
    from app.application.event_bus import EventBus
    from app.infrastructure.system.persisted_state import AuditLogHandler

    bus = EventBus()
    handler = AuditLogHandler()
    bus.subscribe(ControlSettingChanged, handler.handle)

    bus.publish(ControlSettingChanged(
        key="api_secret", old_value="old", new_value="new", changed_by="admin", is_secret=True
    ))

    conn = get_connection()
    row = conn.execute(
        "SELECT old_value, new_value FROM audit_log WHERE event_type = 'control_setting_changed' ORDER BY id DESC LIMIT 1"
    ).fetchone()
    conn.close()

    assert row["old_value"] == "[SECRET_UPDATED]"
    assert row["new_value"] == "[SECRET_UPDATED]"


# ---------------------------------------------------------------------------
# Integration: no direct notify imports in application layer
# ---------------------------------------------------------------------------

def test_no_direct_notify_imports_in_application():
    import os
    from pathlib import Path

    app_dir = Path(__file__).parent.parent / "app" / "application"
    found = []
    for py_file in app_dir.rglob("*.py"):
        content = py_file.read_text(encoding="utf-8")
        if "from app.notifications.telegram import notify" in content:
            found.append(str(py_file.relative_to(app_dir.parent.parent)))
    assert not found, f"Found direct notify imports: {found}"
