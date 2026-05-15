# app/interfaces/api/routes/system_routes.py
from fastapi import APIRouter, HTTPException, Depends
from app.api.auth import require_control_key
from app.system.controller import get_controller
from app.container import get_container

router = APIRouter()


@router.get("/health")
def health():
    c = get_container()
    try:
        connected = c.broker._client.ib.isConnected()
    except Exception:
        connected = False
    return {"status": "ok", "connected": connected}


@router.get("/system/status")
def system_status():
    ctrl = get_controller()
    from app.ibkr.client import get_client
    from app.api.capital import get_operating_capital
    try:
        account = get_client().get_account()
        real_cap = account.get("net_liquidation", 0)
        op_cap = get_operating_capital(real_cap)
    except Exception:
        real_cap = 0
        op_cap = 0
    return {
        "paused": ctrl.is_paused,
        "mode": ctrl.mode,
        "ib_connected": False,  # simplified
        "operating_capital": op_cap,
        "daily_pnl_usd": 0,
        "daily_pnl_pct": 0,
        "open_positions": 0,
    }


@router.post("/system/pause", dependencies=[Depends(require_control_key)])
def system_pause():
    get_controller().pause()
    return {"status": "paused"}


@router.post("/system/resume", dependencies=[Depends(require_control_key)])
def system_resume():
    get_controller().resume()
    return {"status": "resumed"}


@router.post("/system/mode/{mode}", dependencies=[Depends(require_control_key)])
def system_mode(mode: str):
    if mode not in ("paper", "live"):
        raise HTTPException(status_code=400, detail="Invalid mode")
    get_controller().set_mode(mode)
    return {"status": "ok", "mode": mode}


@router.post("/notifications/level/{level}")
def notifications_level(level: str):
    from app.notifications.policy import get_policy
    level_map = {"critico": "critical_only", "normal": "normal", "verbose": "verbose"}
    if level not in level_map:
        raise HTTPException(status_code=400, detail="Invalid level")
    get_policy().set_level(level_map[level])
    return {"status": "ok", "level": level_map[level]}
