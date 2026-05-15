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


@router.get("/dashboard", response_class=HTMLResponse)
def dashboard():
    from app.dashboard.html import DASHBOARD_HTML
    return DASHBOARD_HTML


@router.get("/dashboard/data")
def dashboard_data():
    from app.infrastructure.db.compat import get_open_trades, get_daily_pnl, get_pending_signals
    from app.ibkr.market_permissions import get_permissions_report
    return {
        "open_trades": [{"symbol": t.symbol, "action": t.action, "quantity": t.quantity,
                         "entry_price": t.entry_price, "stop_loss_price": t.stop_loss_price,
                         "take_profit_price": t.take_profit_price, "pnl_pct": t.pnl_pct} for t in get_open_trades()],
        "daily_pnl_usd": get_daily_pnl(),
        "pending_signals": len(get_pending_signals()),
        "market_permissions": get_permissions_report(),
    }


@router.get("/dashboard/symbol/{symbol}")
def dashboard_symbol(symbol: str):
    from app.infrastructure.db.compat import get_patterns_for_symbol, get_closed_trades_by_symbol, get_or_create_symbol_parameters
    return {
        "patterns": [{"text": p.pattern_text, "wins": p.win_count, "losses": p.loss_count}
                     for p in get_patterns_for_symbol(symbol.upper())],
        "trades": [{"action": t.action, "pnl_pct": t.pnl_pct, "exit_reason": t.exit_reason}
                   for t in get_closed_trades_by_symbol(symbol.upper())],
        "parameters": get_or_create_symbol_parameters(symbol.upper()).__dict__,
    }


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
