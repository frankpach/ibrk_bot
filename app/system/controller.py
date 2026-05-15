# app/system/controller.py
"""
Controlador del sistema: pause/resume, cambio de modo paper/live, circuit breaker.
Instancia unica compartida entre el bot de Telegram y la API.
"""
import structlog
from app.infrastructure.db.compat import get_control_settings, update_control_setting
from app.notifications.telegram import notify

logger = structlog.get_logger(__name__)

CIRCUIT_BREAKER_PCT = 0.05  # 5% de perdida diaria detiene el sistema


class SystemController:
    def __init__(self, scheduler):
        import app.config.settings as s
        self.scheduler = scheduler

        # Try to load persisted state; fall back to settings/env
        try:
            persisted = get_control_settings()
        except Exception:
            persisted = {}

        if persisted:
            self.is_paused = bool(persisted.get("is_paused", False))
            self.mode = persisted.get("trading_mode", "paper" if s.PAPER_TRADING_ONLY else "live")
        else:
            self.is_paused = False
            self.mode = "paper" if s.PAPER_TRADING_ONLY else "live"

    def _persist_state(self):
        """Write current operational state to control_settings."""
        try:
            update_control_setting("trading_mode", self.mode)
            update_control_setting("is_paused", "1" if self.is_paused else "0")
        except Exception as exc:
            logger.warning(f"Failed to persist system state: {exc}")

    def pause(self):
        for job_id in ("signal_processor", "scanner", "scanner_fetch"):
            try:
                self.scheduler.pause_job(job_id)
            except Exception:
                pass
        self.is_paused = True
        self._persist_state()
        logger.info("System paused")

    def resume(self):
        for job_id in ("signal_processor", "scanner", "scanner_fetch"):
            try:
                self.scheduler.resume_job(job_id)
            except Exception:
                pass
        self.is_paused = False
        self._persist_state()
        logger.info("System resumed")

    def set_mode(self, mode: str):
        if mode not in ("paper", "live"):
            raise ValueError(f"Invalid mode: {mode}")
        import app.config.settings as s
        if mode == "live":
            s.PAPER_TRADING_ONLY = False
            s.REQUIRE_HUMAN_APPROVAL = True
        else:
            s.PAPER_TRADING_ONLY = True
            s.REQUIRE_HUMAN_APPROVAL = False
        self.mode = mode
        self._persist_state()
        logger.info(f"Mode changed to {mode}")

    def check_circuit_breaker(self, daily_pnl: float, capital: float) -> bool:
        """Retorna True si la perdida diaria supera el umbral y pausa el sistema."""
        if daily_pnl >= 0:
            return False
        loss_pct = abs(daily_pnl) / capital
        if loss_pct >= CIRCUIT_BREAKER_PCT:
            self.pause()
            notify(
                f"CIRCUIT BREAKER ACTIVADO\n"
                f"Perdida del dia: ${abs(daily_pnl):.2f} ({loss_pct:.1%})\n"
                f"Limite: {CIRCUIT_BREAKER_PCT:.0%} de ${capital}\n"
                f"Sistema pausado. Usa /reanudar para continuar."
            )
            logger.warning(f"Circuit breaker triggered: {loss_pct:.1%} daily loss")
            return True
        return False

    def status(self) -> dict:
        return {
            "paused": self.is_paused,
            "mode": self.mode,
            "circuit_breaker_threshold": f"{CIRCUIT_BREAKER_PCT:.0%}",
        }


_controller: SystemController | None = None


def get_controller() -> SystemController:
    if _controller is None:
        raise RuntimeError("SystemController not initialized. Call init_controller() first.")
    return _controller


def init_controller(scheduler) -> SystemController:
    global _controller
    _controller = SystemController(scheduler)
    return _controller
