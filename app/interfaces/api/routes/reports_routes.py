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


@router.get("/reports", response_class=HTMLResponse)
def reports_html():
    return "<html><body>Reports placeholder</body></html>"


@router.get("/reports/{report_id}", response_class=HTMLResponse)
def report_by_id(report_id: int):
    from app.infrastructure.db.compat import get_report_by_id
    report = get_report_by_id(report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    return f"<html><body><h1>{report['title']}</h1><pre>{report['content_md']}</pre></body></html>"


@router.delete("/reports/{report_id}")
def delete_report(report_id: int):
    from app.infrastructure.db.compat import delete_report
    ok = delete_report(report_id)
    return {"deleted": ok}
