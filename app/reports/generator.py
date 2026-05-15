"""Pre-market and daily operations report generator."""
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


def generate_pre_market_report(symbols_data: list, ib_client=None) -> int | None:
    """
    Generate a pre-market analysis report for the selected symbols.
    symbols_data: list of dicts with symbol analysis results
    Returns the report id (for Telegram link), or None on failure.
    """
    try:
        from app.infrastructure.db.compat import save_report, get_news_cache, get_scanner_results
        from app.infrastructure.db.compat import get_account_history

        today = datetime.utcnow().strftime("%Y-%m-%d")
        now_str = datetime.utcnow().strftime("%H:%M UTC")

        # Account snapshot for context
        account_hist = get_account_history(days=1)
        acct = account_hist[-1] if account_hist else {}
        nl = acct.get("net_liquidation", 0)
        bp = acct.get("buying_power", 0)

        # Market context from scanner
        gainers = get_scanner_results("gainers")[:3]
        losers = get_scanner_results("losers")[:3]
        sectors = get_scanner_results("sector")

        # Build markdown report
        lines = [
            f"# Reporte Pre-Mercado — {today}",
            f"*Generado: {now_str}*",
            "",
            "---",
            "",
            "## Estado de Cuenta",
            f"| Metrica | Valor |",
            f"|---------|-------|",
            f"| Net Liquidation | ${nl:,.2f} |" if nl else "",
            f"| Buying Power | ${bp:,.2f} |" if bp else "",
            "",
        ]

        # Market context
        if gainers or losers:
            lines += [
                "## Contexto de Mercado",
                "",
                "**Top Gainers:**",
            ]
            for g in gainers:
                pct = g.get("change_pct") or 0
                lines.append(f"- `{g['symbol']}` {pct:+.1f}%")

            lines += ["", "**Top Losers:**"]
            for lo in losers:
                pct = lo.get("change_pct") or 0
                lines.append(f"- `{lo['symbol']}` {pct:+.1f}%")

            if sectors:
                lines += ["", "**Sectores:**"]
                for s in sectors:
                    pct = s.get("change_pct") or 0
                    lines.append(f"- {s.get('name', s['symbol'])}: {pct:+.1f}%")
            lines.append("")

        # Symbols analysis
        lines += [
            "---",
            "",
            f"## Simbolos Analizados ({len(symbols_data)})",
            "",
        ]

        for item in symbols_data:
            symbol = item.get("symbol", "?")
            score = item.get("score")
            rec = item.get("recommendation", "UNKNOWN")
            narrative = item.get("narrative", "Sin analisis disponible.")
            rsi = item.get("rsi")
            vol = item.get("volume_ratio")
            weekly = item.get("weekly_trend", "NEUTRAL")

            rec_emoji = {
                "BUY": "COMPRA", "SELL": "VENTA", "WATCHLIST": "VIGILA",
                "PROPOSE": "PROPONE", "REJECTED": "RECHAZADO", "IGNORE": "IGNORAR"
            }.get(rec, rec)

            score_str = f"{score:.1f}/100" if score is not None else "N/A"

            lines += [
                f"### {symbol} — {rec_emoji}",
                f"**Score:** {score_str} | **Trend:** {weekly}",
            ]
            if rsi is not None:
                if vol is not None:
                    lines.append(f"**RSI:** {rsi:.1f} | **Vol:** {vol:.1f}x")
                else:
                    lines.append(f"**RSI:** {rsi:.1f}")
            lines += [
                "",
                f"> {narrative}",
                "",
            ]

            # Recent news for this symbol
            news = get_news_cache(symbols=[symbol], limit=2)
            if news:
                lines.append("**Noticias recientes:**")
                for n in news:
                    lines.append(f"- {n.get('headline', '')[:80]}")
                lines.append("")

        lines += [
            "---",
            "",
            "*Reporte generado automaticamente por IBKR AI Trader.*",
        ]

        # Try to append trading mode
        try:
            from app.config.settings import PAPER_TRADING_ONLY
            mode = "PAPER" if PAPER_TRADING_ONLY else "LIVE"
            lines.append(f"*Sistema: {mode}*")
        except Exception:
            pass

        content_md = "\n".join(l for l in lines if l is not None)
        title = f"Pre-Mercado {today} — {len(symbols_data)} simbolos"
        report_id = save_report("pre_market", today, title, content_md)
        logger.info(f"Pre-market report saved: id={report_id}")
        return report_id

    except Exception as e:
        logger.error(f"generate_pre_market_report failed: {e}")
        return None


def generate_daily_ops_report(trades_today: list) -> int | None:
    """Generate an end-of-day operations report."""
    try:
        from app.infrastructure.db.compat import save_report, get_account_history

        today = datetime.utcnow().strftime("%Y-%m-%d")
        now_str = datetime.utcnow().strftime("%H:%M UTC")

        wins = [t for t in trades_today if (t.pnl_usd or 0) > 0]
        losses = [t for t in trades_today if (t.pnl_usd or 0) <= 0]
        total_pnl = sum(t.pnl_usd or 0 for t in trades_today)
        win_rate = len(wins) / len(trades_today) * 100 if trades_today else 0

        lines = [
            f"# Reporte de Operaciones — {today}",
            f"*Generado: {now_str}*",
            "",
            "## Resumen del Dia",
            f"| Metrica | Valor |",
            f"|---------|-------|",
            f"| Trades totales | {len(trades_today)} |",
            f"| Ganadores | {len(wins)} |",
            f"| Perdedores | {len(losses)} |",
            f"| Win rate | {win_rate:.1f}% |",
            f"| P&L neto | ${total_pnl:+.2f} |",
            "",
            "## Detalle de Operaciones",
            "",
            "| Simbolo | Accion | Entrada | Salida | P&L | Razon |",
            "|---------|--------|---------|--------|-----|-------|",
        ]

        for t in trades_today:
            result_str = "+" if (t.pnl_usd or 0) > 0 else "-"
            entry = getattr(t, "entry_price", 0) or 0
            exit_p = getattr(t, "exit_price", 0) or 0
            pnl = getattr(t, "pnl_usd", 0) or 0
            lines.append(
                f"| {t.symbol} | {t.action} | ${entry:.2f} | "
                f"${exit_p:.2f} | {result_str} ${abs(pnl):.2f} | {t.exit_reason or '—'} |"
            )

        lines += ["", "---", "*IBKR AI Trader — Reporte Automatico*"]
        content_md = "\n".join(lines)
        title = f"Operaciones {today} — {len(trades_today)} trades, ${total_pnl:+.2f}"
        return save_report("daily_ops", today, title, content_md)

    except Exception as e:
        logger.error(f"generate_daily_ops_report failed: {e}")
        return None
