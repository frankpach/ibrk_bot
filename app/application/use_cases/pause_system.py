# app/application/use_cases/pause_system.py
"""PauseSystemUseCase and ResumeSystemUseCase — idempotent pause/resume."""
from dataclasses import dataclass

import structlog

from app.application.event_bus import EventBus
from app.application.ports.notification_port import INotificationPort
from app.db.database import get_control_settings, update_control_setting
from app.domain.trading.events import SystemPaused, SystemResumed

logger = structlog.get_logger(__name__)

# Jobs that PauseSystemUseCase should pause
_PAUSABLE_JOBS = ("signal_processor", "scanner", "scanner_fetch", "news_fetch")

# Jobs that should NOT be paused
_NON_PAUSABLE_JOBS = ("position_manager", "circuit_breaker")


@dataclass
class PauseResult:
    success: bool
    error: str | None = None


class PauseSystemUseCase:
    def __init__(self, scheduler, notifier: INotificationPort, event_bus: EventBus):
        self._scheduler = scheduler
        self._notifier = notifier
        self._event_bus = event_bus

    def execute(self) -> PauseResult:
        for job_id in _PAUSABLE_JOBS:
            try:
                self._scheduler.pause_job(job_id)
            except Exception as exc:
                logger.warning(f"Failed to pause job {job_id}: {exc}")

        update_control_setting("is_paused", "1")
        self._event_bus.publish(SystemPaused())
        logger.info("System paused")
        return PauseResult(success=True)


class ResumeSystemUseCase:
    def __init__(self, scheduler, notifier: INotificationPort, event_bus: EventBus):
        self._scheduler = scheduler
        self._notifier = notifier
        self._event_bus = event_bus

    def execute(self) -> PauseResult:
        for job_id in _PAUSABLE_JOBS:
            try:
                self._scheduler.resume_job(job_id)
            except Exception as exc:
                logger.warning(f"Failed to resume job {job_id}: {exc}")

        update_control_setting("is_paused", "0")
        self._event_bus.publish(SystemResumed())
        logger.info("System resumed")
        return PauseResult(success=True)
