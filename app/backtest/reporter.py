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

    return (
        f"Backtest {result.symbol} — {result.period_days} dias\n\n"
        f"Operaciones: {result.total_trades} total\n"
        f"  Ganancias: {result.wins} | Perdidas: {result.losses}\n"
        f"  Win rate: {result.win_rate:.1f}%\n\n"
        f"P&L neto: {pnl_emoji}${abs(result.total_pnl_usd):.2f} "
        f"({result.total_pnl_pct:+.1f}% del capital)\n"
        f"Profit factor: {pf_str}\n"
        f"Max drawdown: {result.max_drawdown_pct:.1f}%\n\n"
        f"Promedio ganancia: +{result.avg_win_pct:.1f}%\n"
        f"Promedio perdida: {result.avg_loss_pct:.1f}%\n\n"
        f"Nota: backtest con datos delayed, sin comisiones."
    )


def format_api(result: BacktestResult) -> dict:
    """Formatea el resultado para el endpoint REST."""
    return {
        "symbol": result.symbol,
        "period_days": result.period_days,
        "total_trades": result.total_trades,
        "wins": result.wins,
        "losses": result.losses,
        "win_rate_pct": result.win_rate,
        "total_pnl_usd": result.total_pnl_usd,
        "total_pnl_pct": result.total_pnl_pct,
        "profit_factor": result.profit_factor,
        "max_drawdown_pct": result.max_drawdown_pct,
        "avg_win_pct": result.avg_win_pct,
        "avg_loss_pct": result.avg_loss_pct,
        "note": "Backtest uses delayed daily data. No commissions included.",
    }
