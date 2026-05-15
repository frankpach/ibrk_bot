# app/infrastructure/db/read_models/dashboard_query.py
"""Dashboard read model — aggregates data from multiple tables in ≤3 queries."""
from __future__ import annotations

import dataclasses
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.infrastructure.db.compat import get_connection

logger = logging.getLogger(__name__)


@dataclasses.dataclass(frozen=True)
class DashboardView:
    status: dict
    open_trades: list[dict]
    closed_trades: list[dict]
    signals: list[dict]
    patterns: list[dict]
    position_snapshots: list[dict]
    learning: dict
    account_history: list[dict]
    latest_account: dict
    news: list[dict]
    scanner: dict
    symbols_universe: list[dict]
    ib_connected: bool
    earnings_warnings: dict
    daily_watchlist: list[dict]


class DashboardDataQuery:
    """Read-only query object for the dashboard.

    Uses a single DB connection to run all reads, minimizing round-trips.
    Does NOT import or call any write use cases.
    """

    def execute(self) -> dict:
        conn = get_connection()
        try:
            # Query 1: status + open trades + closed trades + signals + patterns + account
            status = self._build_status(conn)
            open_trades = self._fetch_open_trades(conn)
            closed_trades = self._fetch_closed_trades(conn)
            signals = self._fetch_signals(conn)
            patterns = self._fetch_patterns(conn)
            account_history = self._fetch_account_history(conn)
            latest_account = account_history[-1] if account_history else {}

            # Query 2: position snapshots
            position_snapshots = self._fetch_position_snapshots(conn)

            # Query 3: market cache + symbol universe + watchlist
            news = self._fetch_news(conn)
            scanner = self._fetch_scanner(conn)
            daily_watchlist = self._fetch_daily_watchlist(conn)
            symbols_universe = self._fetch_symbols_universe(conn, open_trades)

            # Learning metrics (file system, no DB)
            learning = self._build_learning()

            # IB connection (lightweight, no DB)
            ib_connected = self._check_ib_connection()

            # Earnings warnings (skip in read model — too slow / requires IB)
            earnings_warnings = {}

            return {
                "status": status,
                "open_trades": open_trades,
                "closed_trades": closed_trades,
                "signals": signals,
                "patterns": patterns,
                "position_snapshots": position_snapshots,
                "learning": learning,
                "account_history": account_history,
                "latest_account": latest_account,
                "news": news,
                "scanner": scanner,
                "symbols_universe": symbols_universe,
                "ib_connected": ib_connected,
                "earnings_warnings": earnings_warnings,
                "daily_watchlist": daily_watchlist,
            }
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    def _build_status(self, conn) -> dict:
        from app.api.capital import get_operating_capital
        from app.config.settings import PAPER_TRADING_ONLY, CAPITAL_CAP

        row = conn.execute(
            "SELECT * FROM account_snapshots ORDER BY date DESC LIMIT 1"
        ).fetchone()

        _nl = float(row["net_liquidation"] if row else 0.0)
        _bp = float(row["buying_power"] if row else 0.0)
        _capital = get_operating_capital(_nl) if _nl else CAPITAL_CAP
        today_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        latest_account_date = str(row["date"] if row else "")

        status = {
            "mode": "paper" if PAPER_TRADING_ONLY else "live",
            "paused": False,
            "daily_pnl_usd": round(float(row["daily_pnl_usd"] if row else 0.0), 2),
            "daily_pnl_pct": round(float(row["daily_pnl_pct"] if row else 0.0), 4),
            "open_positions": 0,
            "operating_capital": _capital,
            "simulated_capital": _capital,
            "net_liquidation": round(_nl, 2),
            "buying_power": round(_bp, 2),
            "ib_data_live": bool(latest_account_date and latest_account_date == today_utc),
            "drawdown_pct": 0.0,
        }

        try:
            from app.system.controller import get_controller
            ctrl = get_controller()
            status["mode"] = ctrl.mode
            status["paused"] = ctrl.is_paused
            status["open_positions"] = len([t for t in conn.execute("SELECT 1 FROM trades WHERE status='OPEN'").fetchall()])
        except RuntimeError:
            status["open_positions"] = len([t for t in conn.execute("SELECT 1 FROM trades WHERE status='OPEN'").fetchall()])

        # Live P&L from position snapshots
        if status["mode"] == "live":
            live_pnl = conn.execute(
                "SELECT SUM(pnl_usd) as total FROM position_snapshots"
            ).fetchone()
            if live_pnl and live_pnl["total"] is not None:
                status["daily_pnl_usd"] = round(float(live_pnl["total"]), 2)
                status["daily_pnl_pct"] = round(float(live_pnl["total"]) / _capital * 100, 4) if _capital else 0.0

        return status

    # ------------------------------------------------------------------
    # Trades
    # ------------------------------------------------------------------

    def _fetch_open_trades(self, conn) -> list[dict]:
        rows = conn.execute(
            """SELECT id, symbol, action, quantity, entry_price, entry_fill_price,
                      stop_loss_price, take_profit_price, signal_strength, opened_at
               FROM trades WHERE status='OPEN' ORDER BY opened_at DESC"""
        ).fetchall()
        out = []
        for r in rows:
            out.append({
                "id": r["id"],
                "trade_id": r["id"],
                "symbol": r["symbol"],
                "action": r["action"],
                "quantity": r["quantity"],
                "entry_price": r["entry_fill_price"] or r["entry_price"],
                "stop_loss_price": r["stop_loss_price"],
                "take_profit_price": r["take_profit_price"],
                "signal_strength": r["signal_strength"],
                "opened_at": r["opened_at"],
            })
        return out

    def _fetch_closed_trades(self, conn) -> list[dict]:
        rows = conn.execute(
            """SELECT symbol, action, pnl_usd, pnl_pct, exit_reason, closed_at
               FROM trades WHERE status='CLOSED' ORDER BY closed_at DESC LIMIT 8"""
        ).fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Signals & Patterns
    # ------------------------------------------------------------------

    def _fetch_signals(self, conn) -> list[dict]:
        rows = conn.execute(
            """SELECT symbol, strength, rsi, volume_ratio, extra_indicators, created_at
               FROM signals WHERE processed=0 ORDER BY created_at DESC LIMIT 50"""
        ).fetchall()
        out = []
        for r in rows:
            out.append({
                "symbol": r["symbol"],
                "strength": r["strength"],
                "rsi": r["rsi"],
                "volume_ratio": r["volume_ratio"],
                "extra_indicators": r["extra_indicators"] or "{}",
                "created_at": r["created_at"],
            })
        return out

    def _fetch_patterns(self, conn) -> list[dict]:
        # Get patterns for first 8 approved symbols
        syms = conn.execute(
            "SELECT symbol FROM symbol_config WHERE approved=1 LIMIT 8"
        ).fetchall()
        out = []
        for s in syms:
            row = conn.execute(
                """SELECT symbol, pattern_text, win_count, loss_count
                   FROM patterns WHERE symbol=? ORDER BY updated_at DESC LIMIT 1""",
                (s["symbol"],)
            ).fetchone()
            if row:
                out.append({
                    "symbol": row["symbol"],
                    "pattern_text": row["pattern_text"],
                    "wins": row["win_count"],
                    "losses": row["loss_count"],
                })
        return out

    # ------------------------------------------------------------------
    # Account
    # ------------------------------------------------------------------

    def _fetch_account_history(self, conn) -> list[dict]:
        rows = conn.execute(
            "SELECT * FROM account_snapshots ORDER BY date DESC LIMIT 30"
        ).fetchall()
        return list(reversed([dict(r) for r in rows]))

    # ------------------------------------------------------------------
    # Position snapshots
    # ------------------------------------------------------------------

    def _fetch_position_snapshots(self, conn) -> list[dict]:
        rows = conn.execute("SELECT * FROM position_snapshots").fetchall()
        out = []
        for r in rows:
            out.append({
                "trade_id": r["trade_id"],
                "symbol": r["symbol"],
                "current_price": r["current_price"],
                "pnl_usd": r["pnl_usd"],
                "pnl_pct": r["pnl_pct"],
                "updated_at": r["updated_at"],
            })
        return out

    # ------------------------------------------------------------------
    # Market cache
    # ------------------------------------------------------------------

    def _fetch_news(self, conn) -> list[dict]:
        # News for approved symbols (last 20)
        syms = [r["symbol"] for r in conn.execute(
            "SELECT symbol FROM symbol_config WHERE approved=1"
        ).fetchall()]
        if not syms:
            return []
        placeholders = ",".join("?" * len(syms))
        rows = conn.execute(
            f"""SELECT symbol, headline, provider, sentiment, fetched_at, url
                FROM news_cache WHERE symbol IN ({placeholders})
                ORDER BY fetched_at DESC LIMIT 20""",
            syms,
        ).fetchall()
        return [dict(r) for r in rows]

    def _fetch_scanner(self, conn) -> dict:
        scanner = {}
        for scan_type in ("most_active", "top_movers", "gainers", "losers", "sector", "implied_move"):
            rows = conn.execute(
                """SELECT symbol, name, change_pct, volume_ratio, extra_json, fetched_at
                   FROM scanner_results WHERE scan_type=? ORDER BY fetched_at DESC LIMIT 50""",
                (scan_type,),
            ).fetchall()
            scanner[scan_type] = [dict(r) for r in rows]
        return scanner

    def _fetch_daily_watchlist(self, conn) -> list[dict]:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        rows = conn.execute(
            """SELECT symbol, score, signal_strength, change_pct, volume_ratio, reason
               FROM daily_watchlist WHERE date=? ORDER BY score DESC LIMIT 8""",
            (today,),
        ).fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Symbol universe
    # ------------------------------------------------------------------

    def _fetch_symbols_universe(self, conn, open_trades: list[dict]) -> list[dict]:
        open_symbols = {t["symbol"] for t in open_trades}
        rows = conn.execute(
            """SELECT symbol, stop_loss_pct, take_profit_pct, trade_count,
                      backtest_calibrated, backtest_calibrated_at, backtest_profit_factor,
                      momentum_mult, trend_mult, volume_mult, volatility_mult
               FROM symbol_parameters"""
        ).fetchall()

        # Win rates per symbol (last 20 closed trades)
        win_rates = {}
        for sym in {r["symbol"] for r in rows}:
            tr = conn.execute(
                "SELECT pnl_pct FROM trades WHERE symbol=? AND status='CLOSED' ORDER BY closed_at DESC LIMIT 20",
                (sym,)
            ).fetchall()
            if tr:
                wins = sum(1 for t in tr if (t["pnl_pct"] or 0) > 0)
                win_rates[sym] = round(wins / len(tr), 3)

        out = []
        for r in rows:
            sym = r["symbol"]
            multipliers = {}
            for k in ("momentum", "trend", "volume", "volatility"):
                val = r[f"{k}_mult"] or 1.0
                if abs(val - 1.0) > 0.05:
                    multipliers[k] = round(val, 3)
            out.append({
                "symbol": sym,
                "backtest_calibrated": bool(r["backtest_calibrated"]),
                "backtest_calibrated_at": r["backtest_calibrated_at"],
                "backtest_profit_factor": r["backtest_profit_factor"],
                "stop_loss_pct": r["stop_loss_pct"],
                "take_profit_pct": r["take_profit_pct"],
                "trade_count": r["trade_count"],
                "win_rate": win_rates.get(sym),
                "multipliers_drifted": multipliers,
                "is_open": sym in open_symbols,
            })
        out.sort(key=lambda item: (not item["is_open"], item["symbol"]))
        return out

    # ------------------------------------------------------------------
    # Learning
    # ------------------------------------------------------------------

    def _build_learning(self) -> dict:
        learning = {"model_trained": False, "win_rates": {}, "total_trades": 0, "pkl_age_hours": None}
        try:
            pkl = Path("models/signal_filter.pkl")
            if pkl.exists():
                import time
                age_h = (time.time() - pkl.stat().st_mtime) / 3600
                learning["model_trained"] = True
                learning["pkl_age_hours"] = round(age_h, 1)
        except Exception:
            pass
        return learning

    # ------------------------------------------------------------------
    # IB connection
    # ------------------------------------------------------------------

    def _check_ib_connection(self) -> bool:
        try:
            from app.ibkr.client import get_client
            c = get_client()
            return bool(c.ib.isConnected())
        except Exception:
            return False
