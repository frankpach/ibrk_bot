# app/bootstrap/scheduler_setup.py
"""Named scheduler job functions."""
import logging
from datetime import date, datetime

# Module-level reference to the running scheduler (set by runner.py)
_scheduler_instance = None


def set_scheduler(scheduler) -> None:
    global _scheduler_instance
    _scheduler_instance = scheduler


def get_scheduler():
    return _scheduler_instance

from app.config.settings import SCAN_INTERVAL_MINUTES, POSITION_CHECK_MINUTES, CAPITAL_CAP, MARKET_TZ
from app.scanner.preprocessor import run_scan
from app.scanner.market_open_selector import select_top_symbols
from app.positions.manager import check_positions
from app.llm.loop import process_pending_signals
from app.alerts.manager import check_all_alerts
from app.reports.weekly import send_weekly_report
from app.infrastructure.db.compat import get_daily_pnl, get_active_alerts, mark_alert_triggered
from app.api.capital import get_operating_capital
from app.system.controller import get_controller
from app.system.reconciler import reconcile_positions
from app.notifications.telegram import notify

logger = logging.getLogger(__name__)


class SchedulerJobs:
    def __init__(self, ib_client_ref):
        self._ref = ib_client_ref
        self._last_connected_at = time.time() if (ib_client_ref["client"] and ib_client_ref["client"].ib.isConnected()) else None
        self._missing_scan_jobs = []

    def safe_run_scan(self):
        client = self._ref["client"]
        if not client:
            logger.warning("run_scan omitted: no IB connection")
            return
        try:
            if not client.ib.isConnected():
                raise ConnectionError("IB disconnected")
            run_scan(client)
        except Exception as e:
            logger.error(f"run_scan failed: {e}")

    def check_circuit_breaker(self):
        daily_pnl = get_daily_pnl()
        client = self._ref["client"]
        try:
            _acct = client.get_account() if client else {}
            _cap = get_operating_capital(_acct.get("net_liquidation", CAPITAL_CAP))
        except Exception:
            _cap = CAPITAL_CAP
        get_controller().check_circuit_breaker(daily_pnl, _cap)

    def run_reconciliation(self):
        client = self._ref["client"]
        if client:
            try:
                reconcile_positions(client)
            except Exception as e:
                logger.error(f"Reconciliation failed: {e}")

    def send_digest(self):
        from app.infrastructure.db.compat import get_open_trades
        from app.notifications.policy import get_digest_generator
        try:
            open_trades = get_open_trades() or []
            daily_pnl = get_daily_pnl()
            msg = get_digest_generator().generate_digest(
                open_trades=open_trades, daily_pnl=daily_pnl,
                signals_processed=0, system_status="OK",
            )
            notify(msg)
        except Exception as e:
            logger.error(f"Digest failed: {e}")

    def run_news_fetch(self):
        if not self._is_market_hours():
            return
        try:
            dl = self._ref.get("data_layer")
            if dl:
                from app.scanner.news_fetcher import fetch_and_cache_news
                fetch_and_cache_news(dl)
        except Exception as e:
            logger.error(f"News fetch error: {e}")

    def run_scanner_fetch(self):
        if not self._is_market_hours():
            return
        try:
            dl = self._ref.get("data_layer")
            if dl:
                from app.scanner.market_scanner import fetch_and_cache_scanner, fetch_and_cache_sectors, fetch_implied_move
                from app.infrastructure.db.compat import get_approved_symbols
                fetch_and_cache_scanner(dl)
                fetch_and_cache_sectors(dl)
                syms = get_approved_symbols()[:10]
                fetch_implied_move(dl, syms)
        except Exception as e:
            logger.error(f"Scanner fetch error: {e}")

    def run_opportunity_scan(self):
        if not self._is_market_hours():
            return
        try:
            dl = self._ref.get("data_layer")
            if not dl:
                return
            from app.scanner.opportunity_scanner import run_opportunity_scan, scan_news_triggered_opportunities, scan_correlation_lags, notify_opportunities
            movers = run_opportunity_scan(dl, self._ref.get("client"))
            news_opps = scan_news_triggered_opportunities(dl)
            lag_opps = scan_correlation_lags(dl)
            all_opps = {}
            for opp in movers + news_opps + lag_opps:
                sym = opp["symbol"]
                if sym not in all_opps or opp["score"] > all_opps[sym]["score"]:
                    all_opps[sym] = opp
            new_opportunities = list(all_opps.values())
            if new_opportunities:
                from app.config.settings import API_BASE
                notify_opportunities(new_opportunities, API_BASE)
                logger.info(f"Opportunity scan: {len(new_opportunities)} new candidates")
        except Exception as e:
            logger.error(f"Opportunity scan error: {e}")

    def run_permission_discovery(self):
        client = self._ref["client"]
        if not client:
            logger.warning("run_permission_discovery omitted: no IB connection")
            return
        try:
            from app.ibkr.market_permissions import run_permission_discovery
            run_permission_discovery(client)
        except Exception as e:
            logger.error(f"run_permission_discovery failed: {e}")

    def run_learning_cycle(self):
        try:
            dl = self._ref.get("data_layer")
            ib_client = self._ref.get("client")
            if dl:
                from app.ml.cycle import run_learning_cycle
                run_learning_cycle(dl, ib_client=ib_client)
        except Exception as e:
            logger.error(f"Learning cycle error: {e}")

    def run_symbol_inactivity_cleanup(self):
        """Deactivate symbols with no activity in the last 90 days."""
        try:
            from app.infrastructure.db.compat import cleanup_inactive_symbols
            deactivated = cleanup_inactive_symbols(days=90)
            if deactivated:
                symbols_str = ", ".join(deactivated)
                notify(
                    f"🧹 Limpieza semanal de universo\n"
                    f"{len(deactivated)} símbolo(s) desactivado(s) por inactividad (+90 días):\n"
                    f"{symbols_str}"
                )
                logger.info(f"Symbol inactivity cleanup: deactivated {len(deactivated)} symbols: {deactivated}")
            else:
                logger.info("Symbol inactivity cleanup: no inactive symbols found")
        except Exception as e:
            logger.error(f"Symbol inactivity cleanup error: {e}")

    def safe_select_top_symbols(self, market_key: str, session_date=None):
        client = self._ref["client"]
        dl = self._ref["data_layer"]
        if not client or not dl:
            logger.warning(f"Pre-open scan {market_key} omitted: no IB connection")
            self._missing_scan_jobs.append((market_key, session_date or date.today().isoformat()))
            notify(f"⚠️ Pre-open scan {market_key} NO ejecutado (sin IB Gateway).")
            return
        try:
            if not client.ib.isConnected():
                raise ConnectionError("IB Gateway disconnected")
            select_top_symbols(market_key, client, dl, session_date=session_date)
        except Exception as e:
            logger.error(f"Pre-open scan {market_key} failed: {e}")
            self._missing_scan_jobs.append((market_key, session_date or date.today().isoformat()))

    def _is_market_hours(self) -> bool:
        now = datetime.now(MARKET_TZ)
        if now.weekday() >= 5:
            return False
        return 9 <= now.hour < 17


def register_scheduler_jobs(scheduler, ib_client_ref, data_layer):
    jobs = SchedulerJobs(ib_client_ref)
    scheduler.add_job(jobs.safe_run_scan, "interval", minutes=SCAN_INTERVAL_MINUTES, id="scanner")
    scheduler.add_job(check_positions, "interval", minutes=POSITION_CHECK_MINUTES, id="position_manager")
    scheduler.add_job(process_pending_signals, "interval", minutes=SCAN_INTERVAL_MINUTES, id="signal_processor")
    scheduler.add_job(jobs.check_circuit_breaker, "interval", minutes=POSITION_CHECK_MINUTES, id="circuit_breaker")
    scheduler.add_job(lambda: check_all_alerts(get_active_alerts, mark_alert_triggered), "interval", minutes=POSITION_CHECK_MINUTES, id="alert_checker")
    scheduler.add_job(lambda: send_weekly_report(get_operating_capital((ib_client_ref["client"].get_account() if ib_client_ref["client"] else {}).get("net_liquidation", CAPITAL_CAP))), "cron", day_of_week="mon", hour=8, minute=0, timezone=MARKET_TZ, id="weekly_report")
    scheduler.add_job(jobs.send_digest, "cron", hour="10,14", minute=0, timezone=MARKET_TZ, id="digest_job", replace_existing=True)
    scheduler.add_job(jobs.run_symbol_inactivity_cleanup, "cron", day_of_week="mon", hour=17, minute=30, timezone=MARKET_TZ, id="symbol_inactivity_cleanup", replace_existing=True)
    scheduler.add_job(jobs.run_news_fetch, "interval", minutes=30, id="news_fetch", replace_existing=True)
    scheduler.add_job(jobs.run_scanner_fetch, "interval", minutes=15, id="scanner_fetch", replace_existing=True)
    scheduler.add_job(jobs.run_opportunity_scan, "interval", minutes=60, id="opportunity_scan", replace_existing=True)
    scheduler.add_job(jobs.run_permission_discovery, "cron", day_of_week="mon-fri", hour=7, minute=50, timezone=MARKET_TZ, id="market_permissions_daily")
    if data_layer:
        from app.analysis.admission import run_daily_discovery
        from app.analysis.evaluator import run_return_evaluator
        scheduler.add_job(run_daily_discovery, "cron", day_of_week="mon-fri", hour=8, minute=0, timezone=MARKET_TZ, id="daily_discovery")
        scheduler.add_job(run_return_evaluator, "cron", hour=6, minute=0, timezone=MARKET_TZ, id="return_evaluator")
        scheduler.add_job(jobs.run_learning_cycle, "cron", hour=17, minute=5, timezone=MARKET_TZ, id="learning_cycle", replace_existing=True)
    # Pre-open scans
    scheduler.add_job(lambda: jobs.safe_select_top_symbols("STK_US"), trigger="cron", hour=9, minute=15, day_of_week="mon-fri", timezone=MARKET_TZ, id="preopen_stk_us", replace_existing=True)
    scheduler.add_job(lambda: jobs.safe_select_top_symbols("FUT_US"), trigger="cron", hour=17, minute=45, day_of_week="0-3,6", timezone=MARKET_TZ, id="preopen_fut_us", replace_existing=True)
    scheduler.add_job(lambda: jobs.safe_select_top_symbols("CASH_FX"), trigger="cron", hour=16, minute=45, day_of_week="0-3,6", timezone=MARKET_TZ, id="preopen_cash_fx", replace_existing=True)
    scheduler.add_job(lambda: jobs.safe_select_top_symbols("CRYPTO"), trigger="cron", hour=23, minute=45, timezone="UTC", id="preopen_crypto", replace_existing=True)
    return jobs
