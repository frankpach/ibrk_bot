# app/interfaces/api/routes/reports_routes.py
import os
from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from app.container import get_container

router = APIRouter()


@router.get("/logs")
def get_logs(lines: int = 100):
    log_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), "bot.log")
    try:
        with open(log_path, "r", encoding="utf-8") as f:
            return {"lines": f.readlines()[-lines:]}
    except Exception:
        return {"lines": []}



@router.get("/reports/list")
def reports_list():
    from app.infrastructure.db.compat import get_reports
    return get_reports(limit=20)


# /reports, /reports/{id}, DELETE /reports/{id} are handled by app/api/main.py
# to avoid duplicate route conflicts — do not add them here.
