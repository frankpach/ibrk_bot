# app/interfaces/api/routes/control_routes.py
"""Control plane routes — /control/* endpoints."""
from fastapi import APIRouter, Header, HTTPException, Depends, Query
from pydantic import BaseModel

from app.api.auth import require_control_key, require_admin_key
from app.application.event_bus import EventBus
from app.application.services.risk_service import RiskService
from app.application.use_cases.update_control_setting import (
    UpdateControlSettingUseCase,
    UpdateSettingCommand,
)
from app.application.use_cases.control_queries import (
    GetSystemStatusQuery,
    GetAllSettingsQuery,
    GetSettingQuery,
    GetSchedulerStatusQuery,
    TriggerJobUseCase,
    GetAuditLogQuery,
    ResetCircuitBreakerUseCase,
)
from app.application.use_cases.change_mode import ChangeTradingModeUseCase
from app.application.use_cases.pause_system import PauseSystemUseCase, ResumeSystemUseCase
from app.infrastructure.system.secret_manager import SecretManager
from fastapi.responses import HTMLResponse

router = APIRouter(prefix="/control", tags=["control"])


@router.get("", response_class=HTMLResponse)
def control_page():
    """Serve the Control Plane frontend HTML."""
    from app.api.control_plane import render_control_html
    return HTMLResponse(content=render_control_html())


# ---------------------------------------------------------------------------
# DTOs
# ---------------------------------------------------------------------------

class UpdateSettingRequest(BaseModel):
    value: str


class UpdateSettingResponse(BaseModel):
    key: str
    success: bool
    requires_restart: bool = False
    message: str = ""
    error: str | None = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_secret_manager() -> SecretManager | None:
    try:
        return SecretManager()
    except RuntimeError:
        return None


def _get_event_bus() -> EventBus:
    from app.container import get_container
    return get_container().event_bus


def _get_scheduler():
    from app.bootstrap.scheduler_setup import get_scheduler
    return get_scheduler()


def _get_broker_client():
    from app.ibkr.client import get_client
    return get_client()


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/status")
def control_status():
    """Public endpoint — returns current system status."""
    query = GetSystemStatusQuery(broker_client=_get_broker_client())
    return query.execute()


@router.get("/settings")
def control_settings_list():
    """Public endpoint — returns all settings with secrets masked."""
    sm = _get_secret_manager()
    query = GetAllSettingsQuery(secret_manager=sm)
    return {"settings": query.execute()}


@router.get("/settings/{key}")
def control_setting_get(key: str):
    """Public endpoint — returns a single setting. Secrets are masked."""
    sm = _get_secret_manager()
    query = GetSettingQuery(secret_manager=sm)
    result = query.execute(key)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Setting '{key}' not found")
    return result


@router.put("/settings/{key}")
def control_setting_update(
    key: str,
    req: UpdateSettingRequest,
    x_control_key: str | None = Header(default=None),
    x_admin_key: str | None = Header(default=None),
):
    """Updates a setting value.

    - Non-secret, hot-reloadable settings: Control Key sufficient.
    - Secrets and infrastructure settings: Admin Key required.
    """
    from app.application.services.setting_validator import SETTING_REGISTRY
    from app.config.settings import API_CONTROL_KEY, API_ADMIN_KEY

    definition = SETTING_REGISTRY.get(key)
    is_secret = definition.is_secret if definition else False
    requires_admin = is_secret or (definition.requires_restart if definition else False)

    # Base auth: control key
    if not API_CONTROL_KEY or not x_control_key or x_control_key != API_CONTROL_KEY:
        raise HTTPException(status_code=401, detail="Invalid or missing X-Control-Key")

    # Admin auth for secrets / infra
    if requires_admin:
        if not API_ADMIN_KEY or not x_admin_key or x_admin_key != API_ADMIN_KEY:
            raise HTTPException(status_code=403, detail="Admin Key required for this setting")
        changed_by = "admin_key"
    else:
        changed_by = "control_key"

    sm = _get_secret_manager()
    use_case = UpdateControlSettingUseCase(
        event_bus=_get_event_bus(),
        secret_manager=sm,
    )
    result = use_case.execute(
        UpdateSettingCommand(key=key, value=req.value, changed_by=changed_by)
    )
    if not result.success:
        raise HTTPException(status_code=422, detail={"key": key, "error": result.error})
    return UpdateSettingResponse(
        key=result.key,
        success=result.success,
        requires_restart=result.requires_restart,
        message=result.message,
    )


@router.get("/jobs")
def control_jobs_list():
    """Public endpoint — returns APScheduler job status."""
    scheduler = _get_scheduler()
    query = GetSchedulerStatusQuery(scheduler=scheduler)
    return {"jobs": query.execute()}


# Metadata for each pre-open market job: label, schedule description, days, timezone
_PREOPEN_META = {
    "preopen_stk_us": {
        "market_key": "STK_US",
        "label": "Acciones US",
        "schedule": "09:15 ET",
        "days": "Lun – Vie",
        "timezone": "America/New_York",
        "ib_key": "STK_US",
    },
    "preopen_fut_us": {
        "market_key": "FUT_US",
        "label": "Futuros US",
        "schedule": "17:45 ET",
        "days": "Dom – Jue",
        "timezone": "America/New_York",
        "ib_key": "FUT_US",
    },
    "preopen_cash_fx": {
        "market_key": "CASH_FX",
        "label": "Forex",
        "schedule": "16:45 ET",
        "days": "Dom – Jue",
        "timezone": "America/New_York",
        "ib_key": "CASH_FX",
    },
    "preopen_crypto": {
        "market_key": "CRYPTO",
        "label": "Crypto",
        "schedule": "23:45 UTC",
        "days": "Diario",
        "timezone": "UTC",
        "ib_key": "CRYPTO",
    },
}


@router.get("/markets")
def control_markets_list():
    """
    Returns pre-open market jobs enriched with:
    - Account permission (operable by this account per IB Gateway cache)
    - Cron schedule description
    - Next scheduled run
    - Last run timestamp
    """
    from app.infrastructure.db.compat import get_market_permissions, get_control_setting

    scheduler = _get_scheduler()

    # Build permission map from DB cache {key -> available bool}
    try:
        perms_rows = get_market_permissions()
        perm_map = {r["key"]: r.get("available", False) for r in perms_rows}
    except Exception:
        perm_map = {}

    markets = []
    for job_id, meta in _PREOPEN_META.items():
        # Scheduler info
        next_run = None
        if scheduler:
            job = scheduler.get_job(job_id)
            if job and job.next_run_time:
                next_run = job.next_run_time.isoformat()

        # Last run from control_settings
        last_run = None
        try:
            row = get_control_setting(f"job_status_{job_id}")
            if row:
                last_run = row.get("updated_at")
        except Exception:
            pass

        # Operable: True if IB permissions cache says yes, or cache is empty (unknown)
        ib_key = meta["ib_key"]
        if perm_map:
            operable = perm_map.get(ib_key, False)
        else:
            operable = None  # unknown — no cache yet

        markets.append({
            "job_id": job_id,
            "market_key": meta["market_key"],
            "label": meta["label"],
            "schedule": meta["schedule"],
            "days": meta["days"],
            "timezone": meta["timezone"],
            "operable": operable,
            "next_run": next_run,
            "last_run": last_run,
        })

    return {"markets": markets}


class RescheduleRequest(BaseModel):
    hour: int    # 0-23
    minute: int  # 0-59


@router.put("/markets/{job_id}/schedule", dependencies=[Depends(require_control_key)])
def control_market_reschedule(job_id: str, req: RescheduleRequest):
    """
    Control Key required — changes the cron hour/minute for a pre-open market job.
    Takes effect immediately (hot reschedule via APScheduler) and persists in
    control_settings so the new schedule survives service restarts.
    """
    from app.infrastructure.db.compat import update_control_setting_full

    if job_id not in _PREOPEN_META:
        raise HTTPException(status_code=404, detail=f"Market job '{job_id}' not found")
    if not (0 <= req.hour <= 23) or not (0 <= req.minute <= 59):
        raise HTTPException(status_code=422, detail="hour must be 0-23, minute must be 0-59")

    scheduler = _get_scheduler()
    if scheduler is None:
        raise HTTPException(status_code=503, detail="Scheduler not available")

    job = scheduler.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not registered in scheduler")

    meta = _PREOPEN_META[job_id]
    # Keep existing day_of_week and timezone — only change hour/minute
    trigger_kwargs = {
        "trigger": "cron",
        "hour": req.hour,
        "minute": req.minute,
        "timezone": meta["timezone"],
    }
    # day_of_week differs per market
    dow_map = {
        "preopen_stk_us":  "mon-fri",
        "preopen_fut_us":  "0-3,6",
        "preopen_cash_fx": "0-3,6",
        "preopen_crypto":  "*",
    }
    if dow_map.get(job_id, "*") != "*":
        trigger_kwargs["day_of_week"] = dow_map[job_id]

    job.reschedule(**trigger_kwargs)

    # Persist so runner.py picks it up on restart
    schedule_str = f"{req.hour:02d}:{req.minute:02d}"
    update_control_setting_full(
        key=f"preopen_schedule_{job_id}",
        value=schedule_str,
        updated_by="control_key",
    )

    next_run = job.next_run_time.isoformat() if job.next_run_time else None
    return {
        "job_id": job_id,
        "label": meta["label"],
        "schedule": f"{req.hour:02d}:{req.minute:02d} {meta['timezone'].split('/')[-1]}",
        "next_run": next_run,
    }


@router.post("/jobs/{job_id}/trigger", dependencies=[Depends(require_control_key)])
def control_job_trigger(job_id: str):
    """Control Key required — manually triggers a scheduled job."""
    scheduler = _get_scheduler()
    use_case = TriggerJobUseCase(scheduler=scheduler)
    result = use_case.execute(job_id)
    if not result["success"]:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@router.post("/pause", dependencies=[Depends(require_control_key)])
def control_pause():
    """Control Key required — pauses trading jobs."""
    scheduler = _get_scheduler()
    from app.container import get_container
    container = get_container()
    use_case = PauseSystemUseCase(
        scheduler=scheduler,
        notifier=container.notifier,
        event_bus=container.event_bus,
    )
    result = use_case.execute()
    return {"success": result.success}


@router.post("/resume", dependencies=[Depends(require_control_key)])
def control_resume():
    """Control Key required — resumes trading jobs."""
    scheduler = _get_scheduler()
    from app.container import get_container
    container = get_container()
    use_case = ResumeSystemUseCase(
        scheduler=scheduler,
        notifier=container.notifier,
        event_bus=container.event_bus,
    )
    result = use_case.execute()
    return {"success": result.success}


@router.post("/mode/{mode}", dependencies=[Depends(require_admin_key)])
def control_mode(mode: str):
    """Admin Key required — changes trading mode (paper/live)."""
    scheduler = _get_scheduler()
    from app.container import get_container
    container = get_container()
    use_case = ChangeTradingModeUseCase(
        scheduler=scheduler,
        broker=container.broker,
        notifier=container.notifier,
        event_bus=container.event_bus,
        changed_by="admin_key",
    )
    result = use_case.execute(mode)
    return {
        "success": result.success,
        "warning": result.warning,
        "error": result.error,
    }


@router.post("/circuit-breaker/reset", dependencies=[Depends(require_control_key)])
def control_circuit_breaker_reset():
    """Control Key required — resets the circuit breaker."""
    use_case = ResetCircuitBreakerUseCase()
    return use_case.execute()


@router.get("/audit", dependencies=[Depends(require_control_key)])
def control_audit(
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
):
    """Control Key required — returns paginated audit log."""
    query = GetAuditLogQuery()
    return query.execute(limit=limit, offset=offset)
