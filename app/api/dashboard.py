# app/api/dashboard.py
"""
Genera el HTML del dashboard de trading.
HTML puro sin frameworks — legible en movil.
Accesible en http://<pi-ip>:8088/dashboard
Auto-refresh cada 60 segundos.
"""
from datetime import datetime


def _row(cells: list, header: bool = False) -> str:
    tag = "th" if header else "td"
    inner = "".join(f"<{tag}>{c}</{tag}>" for c in cells)
    return f"<tr>{inner}</tr>"


def _table(headers: list, rows: list) -> str:
    if not rows:
        return ""
    head = _row(headers, header=True)
    body = "".join(_row(r) for r in rows)
    return f"<table><thead>{head}</thead><tbody>{body}</tbody></table>"


def _color(value: float) -> str:
    return "#4f4" if value >= 0 else "#f44"


def render_dashboard(
    status: dict,
    trades: list,
    closed_trades: list,
    signals: list,
    patterns: list,
) -> str:
    mode = status.get("mode", "paper").upper()
    paused = "PAUSADO" if status.get("paused") else "Activo"
    daily_pnl = float(status.get("daily_pnl_usd") or 0.0)
    daily_pct = float(status.get("daily_pnl_pct") or 0.0)
    capital = status.get("simulated_capital", 500)
    open_pos = status.get("open_positions", 0)
    pnl_color = _color(daily_pnl)

    # Posiciones abiertas
    if trades:
        trade_rows = [
            [t["symbol"], t["action"], t["quantity"],
             f"${float(t['entry_price']):.2f}", f"${float(t['stop_loss_price']):.2f}",
             f"${float(t['take_profit_price']):.2f}", t["signal_strength"]]
            for t in trades
        ]
        trades_html = _table(
            ["Simbolo", "Accion", "Qty", "Entrada", "SL", "TP", "Senal"],
            trade_rows
        )
    else:
        trades_html = "<p>Sin posiciones abiertas</p>"

    # Historial reciente
    if closed_trades:
        hist_rows = [
            [t["symbol"], t["action"],
             f'<span style="color:{_color(float(t.get("pnl_usd") or 0))}">'
             f'${float(t.get("pnl_usd") or 0):.2f}</span>',
             t.get("exit_reason", "?"),
             str(t.get("closed_at") or "")[:16]]
            for t in closed_trades[:5]
        ]
        hist_html = _table(["Simbolo", "Accion", "P&L", "Razon", "Fecha"], hist_rows)
    else:
        hist_html = "<p>Sin historial</p>"

    # Señales recientes
    if signals:
        sig_rows = [
            [s["symbol"], f'<b>{s["strength"]}</b>',
             s.get("rsi", "?"), s.get("volume_ratio", "?"),
             str(s.get("created_at") or "")[:16]]
            for s in signals[:5]
        ]
        sig_html = _table(["Simbolo", "Fuerza", "RSI", "Vol", "Hora"], sig_rows)
    else:
        sig_html = "<p>Sin senales recientes</p>"

    # Patrones
    if patterns:
        pat_rows = [
            [p.get("symbol", "?"), p.get("pattern", "?")[:50],
             p.get("wins", 0), p.get("losses", 0)]
            for p in patterns[:5]
        ]
        pat_html = _table(["Simbolo", "Patron", "Wins", "Losses"], pat_rows)
    else:
        pat_html = "<p>Sin patrones aprendidos aun</p>"

    mode_badge = "paper" if mode == "PAPER" else "live"
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta http-equiv="refresh" content="60">
<title>IBKR AI Trader</title>
<style>
  body {{ font-family: monospace; margin: 16px; background: #111; color: #eee; }}
  h1 {{ color: #4af; margin-bottom: 4px; font-size: 1.4em; }}
  h2 {{ color: #aaa; border-bottom: 1px solid #333; padding-bottom: 4px; font-size: 1em; margin-top: 20px; }}
  .status {{ background: #1a1a2e; padding: 12px; border-radius: 6px; margin-bottom: 16px; display: flex; flex-wrap: wrap; gap: 16px; }}
  .stat {{ min-width: 120px; }}
  .stat label {{ color: #888; font-size: 0.8em; display: block; }}
  .stat span {{ font-size: 1.2em; font-weight: bold; }}
  table {{ width: 100%; border-collapse: collapse; margin-bottom: 8px; font-size: 0.82em; overflow-x: auto; display: block; }}
  th {{ background: #1a1a3a; color: #4af; padding: 6px 8px; text-align: left; white-space: nowrap; }}
  td {{ padding: 5px 8px; border-bottom: 1px solid #222; white-space: nowrap; }}
  tr:hover td {{ background: #1a1a1a; }}
  .badge-paper {{ background: #1a3a1a; color: #4f4; padding: 2px 8px; border-radius: 4px; font-size: 0.9em; }}
  .badge-live {{ background: #3a1a1a; color: #f44; padding: 2px 8px; border-radius: 4px; font-size: 0.9em; }}
  p {{ color: #555; margin: 4px 0; }}
  .footer {{ color: #333; font-size: 0.75em; margin-top: 24px; }}
</style>
</head>
<body>
<h1>IBKR AI Trader</h1>
<div class="status">
  <div class="stat">
    <label>Modo</label>
    <span class="badge-{mode_badge}">{mode}</span>
  </div>
  <div class="stat">
    <label>Estado</label>
    <span>{paused}</span>
  </div>
  <div class="stat">
    <label>Capital</label>
    <span>${capital}</span>
  </div>
  <div class="stat">
    <label>P&amp;L hoy</label>
    <span style="color:{pnl_color}">${daily_pnl:.2f} ({daily_pct:.1f}%)</span>
  </div>
  <div class="stat">
    <label>Posiciones</label>
    <span>{open_pos}/3</span>
  </div>
</div>

<h2>Posiciones Abiertas</h2>
{trades_html}

<h2>Historial Reciente</h2>
{hist_html}

<h2>Senales Detectadas</h2>
{sig_html}

<h2>Patrones Aprendidos</h2>
{pat_html}

<p class="footer">Actualiza cada 60s &mdash; {now_str}</p>
</body>
</html>"""
