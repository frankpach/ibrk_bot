# app/reports/weekly.py
"""
Genera y envia el reporte semanal de trading cada lunes 8am ET.
Incluye: operaciones, P&L, win rate, patrones aprendidos.
"""
import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from app.notifications.telegram import notify

logger = logging.getLogger(__name__)
ET = ZoneInfo("America/New_York")


def generate_weekly_report(trades: list, patterns: list, capital: float) -> str:
    """
    Genera el texto del reporte semanal.
    trades: lista de Trade cerrados en la semana
    patterns: lista de Pattern creados en la semana
    capital: capital simulado
    """
    if not trades and not patterns:
        return (
            "Reporte Semanal IBKR AI Trader\n\n"
            "Sin operaciones esta semana.\n"
            "El scanner continua monitoreando el mercado."
        )

    if not trades:
        lines = ["Reporte Semanal IBKR AI Trader", "", "Sin operaciones esta semana."]
        if patterns:
            lines += ["", f"Patrones aprendidos esta semana: {len(patterns)}"]
            for p in patterns[:3]:
                lines.append(f"  - {p.pattern_text[:60]}")
        return "\n".join(lines)

    wins = [t for t in trades if (t.pnl_usd or 0) > 0]
    losses = [t for t in trades if (t.pnl_usd or 0) <= 0]
    total_pnl = sum(t.pnl_usd or 0 for t in trades)
    win_rate = len(wins) / len(trades) * 100 if trades else 0

    symbols = {}
    for t in trades:
        symbols[t.symbol] = symbols.get(t.symbol, 0) + 1
    top_symbols = sorted(symbols.items(), key=lambda x: x[1], reverse=True)[:3]

    lines = [
        "Reporte Semanal IBKR AI Trader",
        "",
        f"Operaciones: {len(trades)} total | {len(wins)} ganancias | {len(losses)} perdidas",
        f"Win rate: {win_rate:.0f}%",
        f"P&L neto: ${total_pnl:.2f} ({total_pnl / capital * 100:.1f}% del capital)",
        "",
        "Detalle:",
    ]

    for t in trades[:5]:
        emoji = "+" if (t.pnl_usd or 0) >= 0 else "-"
        lines.append(
            f"  {emoji} {t.symbol} {t.action} | ${t.pnl_usd:.2f} ({t.exit_reason})"
        )

    if len(trades) > 5:
        lines.append(f"  ... y {len(trades) - 5} operaciones mas")

    if top_symbols:
        lines.append("")
        lines.append("Simbolos mas activos:")
        for sym, count in top_symbols:
            lines.append(f"  {sym}: {count} operacion(es)")

    if patterns:
        lines.append("")
        lines.append(f"Patrones aprendidos esta semana: {len(patterns)}")
        for p in patterns[:3]:
            lines.append(f"  - {p.pattern_text[:60]}")

    return "\n".join(lines)


def get_closed_trades_since(since: datetime) -> list:
    """Retorna trades cerrados desde una fecha."""
    from app.infrastructure.db.compat import get_connection
    from app.db.models import Trade

    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM trades WHERE status='CLOSED' AND closed_at >= ? ORDER BY closed_at DESC",
        (since.isoformat(),)
    ).fetchall()
    conn.close()
    return [Trade(
        id=r["id"], symbol=r["symbol"], action=r["action"],
        quantity=r["quantity"], entry_price=r["entry_price"],
        stop_loss_price=r["stop_loss_price"], take_profit_price=r["take_profit_price"],
        stop_loss_pct=r["stop_loss_pct"], take_profit_pct=r["take_profit_pct"],
        signal_strength=r["signal_strength"], llm_justification=r["llm_justification"],
        status=r["status"], exit_price=r["exit_price"], exit_reason=r["exit_reason"],
        pnl_usd=r["pnl_usd"], pnl_pct=r["pnl_pct"],
        opened_at=datetime.fromisoformat(r["opened_at"]),
        closed_at=datetime.fromisoformat(r["closed_at"]) if r["closed_at"] else None,
        order_id=r["order_id"],
    ) for r in rows]


def send_weekly_report(capital: float = 500.0):
    """Genera y envia el reporte semanal por Telegram."""
    from app.infrastructure.db.compat import get_patterns_for_week

    now = datetime.now(tz=ET)
    week_ago = now - timedelta(days=7)

    try:
        trades = get_closed_trades_since(week_ago)
        patterns = get_patterns_for_week(week_ago)
    except Exception as e:
        logger.error(f"Could not fetch weekly data: {e}")
        trades, patterns = [], []

    report = generate_weekly_report(trades, patterns, capital)
    notify(report)
    logger.info("Weekly report sent")
