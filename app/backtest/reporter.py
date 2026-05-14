# app/backtest/reporter.py
"""Formatea los resultados del backtest para Telegram y API."""
from app.backtest.engine import BacktestResult


def format_telegram(result: BacktestResult) -> str:
    """Formatea el resultado para enviar por Telegram."""
    if result.total_trades == 0:
        return (
            f"Backtest {result.symbol} ({result.period_days} dias)\n\n"
            f"Sin senales generadas en el periodo.\n"
            f"El algoritmo no habria operado este simbolo."
        )

    pnl_emoji = "+" if result.total_pnl_usd >= 0 else "-"
    pf_str = f"{result.profit_factor:.2f}" if result.profit_factor != float("inf") else "inf"
    commissions = result.__dict__.get("total_commissions_usd", None)
    comm_line = f"Comisiones totales: ${commissions:.2f}\n" if commissions is not None else ""

    # Gross PnL (before commissions) for reference
    gross_pnl = sum(t.get("gross_pnl_usd", t.get("pnl_usd", 0)) for t in result.trades)

    return (
        f"Backtest {result.symbol} — {result.period_days} dias\n\n"
        f"Operaciones: {result.total_trades} total\n"
        f"  Ganancias: {result.wins} | Perdidas: {result.losses}\n"
        f"  Win rate: {result.win_rate:.1f}%\n\n"
        f"P&L bruto: ${gross_pnl:+.2f}\n"
        f"{comm_line}"
        f"P&L neto: {pnl_emoji}${abs(result.total_pnl_usd):.2f} "
        f"({result.total_pnl_pct:+.1f}% del capital)\n"
        f"Profit factor: {pf_str}\n"
        f"Max drawdown: {result.max_drawdown_pct:.1f}%\n\n"
        f"Avg ganancia: +{result.avg_win_pct:.1f}% | "
        f"Avg perdida: {result.avg_loss_pct:.1f}%\n\n"
        f"Incluye: slippage 0.1%/lado + comision $1/trade IBKR."
    )


def format_api(result: BacktestResult) -> dict:
    """Formatea el resultado para el endpoint REST."""
    commissions = result.__dict__.get("total_commissions_usd", 0.0)
    gross_pnl = sum(t.get("gross_pnl_usd", t.get("pnl_usd", 0)) for t in result.trades)
    return {
        "symbol": result.symbol,
        "period_days": result.period_days,
        "total_trades": result.total_trades,
        "wins": result.wins,
        "losses": result.losses,
        "win_rate_pct": result.win_rate,
        "gross_pnl_usd": round(gross_pnl, 2),
        "total_commissions_usd": commissions,
        "total_pnl_usd": result.total_pnl_usd,
        "total_pnl_pct": result.total_pnl_pct,
        "profit_factor": result.profit_factor,
        "max_drawdown_pct": result.max_drawdown_pct,
        "avg_win_pct": result.avg_win_pct,
        "avg_loss_pct": result.avg_loss_pct,
        "note": "Includes 0.1% slippage per side + $1 IBKR min commission per trade.",
    }
