# app/application/use_cases/control_queries.py
"""Query use cases for the control plane (read-only operations)."""
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from app.infrastructure.db.compat import get_connection, get_control_settings, get_control_setting
from app.infrastructure.system.secret_manager import SecretManager

_SECRET_MASK = "••••••••"


@dataclass
class SystemStatusView:
    mode: str
    paused: bool
    ib_connected: bool
    ib_port: int
    open_positions: int
    daily_pnl_usd: float
    daily_pnl_pct: float
    circuit_breaker_active: bool
    circuit_breaker_threshold: float


class GetSystemStatusQuery:
    """Returns the current operational status of the trading system."""

    def __init__(self, broker_client=None):
        self._broker = broker_client

    def execute(self) -> dict:
        from app.config.settings import PAPER_TRADING_ONLY, IB_PORT
        from app.infrastructure.db.compat import get_open_trades, get_daily_pnl
        from app.system.controller import get_controller

        open_trades = get_open_trades()
        daily_pnl = get_daily_pnl()

        mode = "paper" if PAPER_TRADING_ONLY else "live"
        paused = False
        try:
            ctrl = get_controller()
            mode = ctrl.mode
            paused = ctrl.is_paused
        except RuntimeError:
            pass

        ib_connected = False
        try:
            if self._broker is not None:
                ib_connected = bool(self._broker.ib.isConnected())
        except Exception:
            pass

        settings = get_control_settings()
        ib_port = int(settings.get("ib_port", IB_PORT))

        return {
            "mode": mode,
            "paused": paused,
            "ib_connected": ib_connected,
            "ib_port": ib_port,
            "open_positions": len(open_trades),
            "daily_pnl_usd": round(daily_pnl, 2),
            "daily_pnl_pct": 0.0,  # computed below if capital available
            "circuit_breaker_active": False,
            "circuit_breaker_threshold": 0.05,
        }


class GetAllSettingsQuery:
    """Returns all control settings, masking secret values."""

    def __init__(self, secret_manager: SecretManager | None = None):
        self._secret_manager = secret_manager

    def execute(self) -> list[dict]:
        conn = get_connection()
        try:
            rows = conn.execute(
                "SELECT key, value, updated_at, updated_by, is_secret, requires_restart FROM control_settings"
            ).fetchall()
        finally:
            conn.close()

        result = []
        for row in rows:
            is_secret = bool(row["is_secret"])
            value = _SECRET_MASK if is_secret else row["value"]
            result.append({
                "key": row["key"],
                "value": value,
                "updated_at": row["updated_at"],
                "updated_by": row["updated_by"],
                "is_secret": is_secret,
                "requires_restart": bool(row["requires_restart"]),
            })
        return result


class GetSettingQuery:
    """Returns a single setting, optionally revealing if decryption failed."""

    def __init__(self, secret_manager: SecretManager | None = None):
        self._secret_manager = secret_manager

    def execute(self, key: str) -> dict | None:
        from app.application.services.setting_validator import SETTING_REGISTRY

        row = get_control_setting(key)
        if row is None:
            return None

        is_secret = row["is_secret"]
        value = row["value"]
        decryption_failed = False

        if is_secret and self._secret_manager is not None:
            if self._secret_manager.is_encrypted(value):
                try:
                    value = self._secret_manager.decrypt(value)
                except Exception:
                    decryption_failed = True
                    value = _SECRET_MASK
            else:
                # Value not encrypted (legacy or misconfiguration)
                value = _SECRET_MASK
        elif is_secret:
            value = _SECRET_MASK

        definition = SETTING_REGISTRY.get(key)

        return {
            "key": key,
            "value": value if not is_secret else _SECRET_MASK,
            "updated_at": row["updated_at"],
            "updated_by": row["updated_by"],
            "is_secret": is_secret,
            "requires_restart": row["requires_restart"],
            "decryption_failed": decryption_failed,
            "type": definition.type.__name__ if definition else "str",
        }


class GetSchedulerStatusQuery:
    """Returns APScheduler job status."""

    def __init__(self, scheduler):
        self._scheduler = scheduler

    def execute(self) -> list[dict]:
        jobs = []
        try:
            for job in self._scheduler.get_jobs():
                job_id = job.id
                last_run = None
                last_status = "ok"
                last_error = None

                # Read persisted job status from control_settings
                row = get_control_setting(f"job_status_{job_id}")
                if row:
                    try:
                        meta = {}  # Could parse JSON in future
                        last_run = row["updated_at"]
                    except Exception:
                        pass

                next_run = job.next_run_time.isoformat() if job.next_run_time else None

                jobs.append({
                    "job_id": job_id,
                    "name": getattr(job, "name", job_id),
                    "last_run": last_run,
                    "next_run": next_run,
                    "last_status": last_status,
                    "last_error": last_error,
                })
        except Exception:
            pass
        return jobs


class TriggerJobUseCase:
    """Manually triggers an APScheduler job and updates its status."""

    def __init__(self, scheduler):
        self._scheduler = scheduler

    def execute(self, job_id: str) -> dict:
        from app.infrastructure.db.compat import update_control_setting_full

        try:
            job = self._scheduler.get_job(job_id)
            if job is None:
                return {"success": False, "error": f"Job '{job_id}' not found"}
            job.modify(next_run_time=datetime.now(timezone.utc))
            update_control_setting_full(
                key=f"job_status_{job_id}",
                value="triggered",
                updated_by="control_key",
            )
            return {"success": True, "job_id": job_id, "message": "Job triggered"}
        except Exception as exc:
            return {"success": False, "error": str(exc)}


class GetAuditLogQuery:
    """Returns paginated audit log entries."""

    def execute(self, limit: int = 50, offset: int = 0) -> dict:
        conn = get_connection()
        try:
            total = conn.execute("SELECT COUNT(*) FROM audit_log").fetchone()[0]
            rows = conn.execute(
                """SELECT id, event_type, entity_type, entity_id,
                          old_value, new_value, changed_by, ip_address, occurred_at
                   FROM audit_log
                   ORDER BY occurred_at DESC
                   LIMIT ? OFFSET ?""",
                (limit, offset),
            ).fetchall()
        finally:
            conn.close()

        entries = []
        for row in rows:
            entries.append({
                "id": row["id"],
                "event_type": row["event_type"],
                "entity_type": row["entity_type"],
                "entity_id": row["entity_id"],
                "old_value": row["old_value"],
                "new_value": row["new_value"],
                "changed_by": row["changed_by"],
                "ip_address": row["ip_address"],
                "occurred_at": row["occurred_at"],
            })

        return {
            "total": total,
            "limit": limit,
            "offset": offset,
            "entries": entries,
        }


class ResetCircuitBreakerUseCase:
    """Resets the circuit breaker state."""

    def __init__(self, event_bus=None):
        self._event_bus = event_bus

    def execute(self) -> dict:
        from app.infrastructure.db.compat import update_control_setting_full
        update_control_setting_full(
            key="circuit_breaker_triggered",
            value="0",
            updated_by="control_key",
        )
        return {"success": True, "message": "Circuit breaker reset"}


class ChangeTradingModeUseCase:
    """Thin wrapper around the existing change_mode use case for the control plane."""
    pass  # Already exists in app.application.use_cases.change_mode
