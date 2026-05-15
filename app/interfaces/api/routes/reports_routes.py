# app/interfaces/api/routes/reports_routes.py
from fastapi import APIRouter

router = APIRouter()


@router.get("/reports/list")
def reports_list():
    from app.infrastructure.db.compat import get_reports
    return get_reports(limit=20)


# /reports, /reports/{id}, DELETE /reports/{id} are handled by app/api/main.py
# to avoid duplicate route conflicts — do not add them here.
