# run.py
import logging
import socket
import threading
import time
import uvicorn
from apscheduler.schedulers.background import BackgroundScheduler

from app.db.database import init_db, get_daily_pnl, init_alerts_table, get_active_alerts, mark_alert_triggered, init_market_permissions_table
from app.ibkr.client import IBKRClient
from app.scanner.preprocessor import run_scan
from app.scanner.market_open_selector import select_top_symbols
from app.positions.manager import check_positions
from app.llm.loop import process_pending_signals
from app.system.controller import init_controller
from app.system.reconciler import reconcile_positions
from app.notifications.telegram import notify
from app.notifications.telegram_bot import start_bot
from app.alerts.manager import check_all_alerts
from app.reports.weekly import send_weekly_report
from app.config.settings import SCAN_INTERVAL_MINUTES, POSITION_CHECK_MINUTES, CAPITAL_CAP, MARKET_TZ
from app.api.capital import get_operating_capital

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s - %(message)s")
logger = logging.getLogger(__name__)

IB_HOST = "127.0.0.1"
IB_PORT = 4002
GATEWAY_CHECK_INTERVAL = 30  # segundos entre reintentos
GATEWAY_MAX_WAIT = 600        # esperar máximo 10 minutos


def _is_gateway_online() -> bool:
    """Verifica si IB Gateway acepta conexiones en el puerto 4002."""
    try:
        with socket.create_connection((IB_HOST, IB_PORT), timeout=3):
            return True
    except (OSError, ConnectionRefusedError):
        return False


def wait_for_gateway() -> bool:
    """
    Espera a que IB Gateway esté disponible.
    Notifica por Telegram si tarda más de 30 segundos.
    Retorna True si conectó, False si agotó el tiempo.
    """
    if _is_gateway_online():
        return True

    logger.warning("IB Gateway not available, waiting...")
    notify(
        "IB Gateway no disponible en el puerto 4002.\n"
        "Esperando hasta 10 minutos...\n"
        "Asegúrate de que IB Gateway esté iniciado y con sesión activa."
    )

    elapsed = 0
    while elapsed < GATEWAY_MAX_WAIT:
        time.sleep(GATEWAY_CHECK_INTERVAL)
        elapsed += GATEWAY_CHECK_INTERVAL
        if _is_gateway_online():
            logger.info(f"IB Gateway online after {elapsed}s")
            notify(f"IB Gateway conectado después de {elapsed}s. Iniciando sistema...")
            return True
        logger.info(f"Still waiting for IB Gateway... ({elapsed}s)")

    notify(
        "No se pudo conectar a IB Gateway después de 10 minutos.\n"
        "El sistema iniciará sin conexión a IB.\n"
        "Usa /estado para verificar el estado."
    )
    return False


def _sunday_reauth_reminder():
    """Envia recordatorio dominical de re-autenticación."""
    from datetime import datetime
    from zoneinfo import ZoneInfo
    now = datetime.now(tz=ZoneInfo("America/New_York"))
    if now.weekday() == 6:  # domingo
        notify(
            "Recordatorio semanal IB Gateway\n\n"
            "IBKR invalida los tokens de seguridad cada domingo.\n"
            "Es posible que necesites re-autenticarte manualmente.\n"
            "Si el sistema deja de funcionar esta noche, abre IB Gateway\n"
            "y aprueba la re-autenticación en tu app móvil de IBKR."
        )


def main():
    logger.info("Initializing database...")
    init_db()
    init_alerts_table()
    init_market_permissions_table()

    # Esperar a IB Gateway antes de continuar
    logger.info("Checking IB Gateway availability...")
    wait_for_gateway()

    logger.info("Connecting to IB Gateway...")
    try:
        ib_client = IBKRClient()
    except Exception as e:
        logger.error(f"Could not connect to IB Gateway: {e}")
        notify(f"Error conectando a IB Gateway: {e}\nEl sistema iniciará en modo limitado.")
        ib_client = None

    if ib_client:
        logger.info("Reconciling positions...")
        reconcile_positions(ib_client)

    # Create data layer for analysis modules
    from app.analysis.data import IBDataLayer
    data_layer = IBDataLayer(ib_client) if ib_client else None

    scheduler = BackgroundScheduler()
    ctrl = init_controller(scheduler)

    def _check_circuit_breaker():
        daily_pnl = get_daily_pnl()
        try:
            _acct = ib_client.get_account() if ib_client else {}
            _cap = get_operating_capital(_acct.get("net_liquidation", CAPITAL_CAP))
        except Exception:
            _cap = CAPITAL_CAP
        ctrl.check_circuit_breaker(daily_pnl, _cap)

    def _check_gateway_and_reconnect():
        """Verifica la conexión a IB Gateway y reconecta si es necesario."""
        if ib_client and not ib_client.ib.isConnected():
            logger.warning("IB Gateway disconnected, attempting reconnect...")
            try:
                ib_client._run_sync(ib_client._connect_async())
                notify("IB Gateway reconectado automáticamente.")
                logger.info("IB Gateway reconnected")
            except Exception as e:
                logger.error(f"Reconnect failed: {e}")

    if ib_client:
        scheduler.add_job(lambda: run_scan(ib_client), "interval", minutes=SCAN_INTERVAL_MINUTES, id="scanner")
    scheduler.add_job(lambda: check_positions(), "interval", minutes=POSITION_CHECK_MINUTES, id="position_manager")
    scheduler.add_job(process_pending_signals, "interval", minutes=SCAN_INTERVAL_MINUTES, id="signal_processor")
    scheduler.add_job(_check_circuit_breaker, "interval", minutes=POSITION_CHECK_MINUTES, id="circuit_breaker")
    scheduler.add_job(
        lambda: check_all_alerts(get_active_alerts, mark_alert_triggered),
        "interval",
        minutes=POSITION_CHECK_MINUTES,
        id="alert_checker",
    )
    scheduler.add_job(
        lambda: send_weekly_report(get_operating_capital(
            (ib_client.get_account() if ib_client else {}).get("net_liquidation", CAPITAL_CAP)
        )),
        "cron",
        day_of_week="mon",
        hour=8,
        minute=0,
        timezone=MARKET_TZ,
        id="weekly_report",
    )
    # Recordatorio dominical 10:00 PM ET
    scheduler.add_job(
        _sunday_reauth_reminder,
        "cron",
        day_of_week="sun",
        hour=22,
        minute=0,
        timezone=MARKET_TZ,
        id="sunday_reminder",
    )
    # Verificar conexión IB cada 5 minutos
    scheduler.add_job(
        _check_gateway_and_reconnect,
        "interval",
        minutes=5,
        id="gateway_watchdog",
    )
    if data_layer:
        from app.analysis.admission import run_daily_discovery
        from app.analysis.evaluator import run_return_evaluator
        scheduler.add_job(
            lambda: run_daily_discovery(data_layer),
            "cron", day_of_week="mon-fri", hour=8, minute=0,
            timezone=MARKET_TZ, id="daily_discovery",
        )
        scheduler.add_job(
            lambda: run_return_evaluator(data_layer),
            "cron", hour=6, minute=0,
            timezone=MARKET_TZ, id="return_evaluator",
        )

    # Descubrir permisos de mercado diariamente a las 7:50am ET (antes de abrir US)
    if ib_client:
        from app.ibkr.market_permissions import run_permission_discovery
        scheduler.add_job(
            lambda: run_permission_discovery(ib_client),
            "cron", day_of_week="mon-fri", hour=7, minute=50,
            timezone=MARKET_TZ, id="market_permissions_daily",
        )

    # Pre-open symbol selection jobs
    # STK_US: 09:15 ET, Mon-Fri
    scheduler.add_job(
        lambda: select_top_symbols("STK_US", ib_client, data_layer),
        trigger="cron",
        hour=9,
        minute=15,
        day_of_week="mon-fri",
        timezone=MARKET_TZ,
        id="preopen_stk_us",
        replace_existing=True,
    )

    # FUT_US: 17:45 ET, Sun-Thu
    scheduler.add_job(
        lambda: select_top_symbols("FUT_US", ib_client, data_layer),
        trigger="cron",
        hour=17,
        minute=45,
        day_of_week="sun-thu",
        timezone=MARKET_TZ,
        id="preopen_fut_us",
        replace_existing=True,
    )

    # CASH_FX: 16:45 ET, Sun-Thu
    scheduler.add_job(
        lambda: select_top_symbols("CASH_FX", ib_client, data_layer),
        trigger="cron",
        hour=16,
        minute=45,
        day_of_week="sun-thu",
        timezone=MARKET_TZ,
        id="preopen_cash_fx",
        replace_existing=True,
    )

    # CRYPTO: 23:45 UTC, daily
    scheduler.add_job(
        lambda: select_top_symbols("CRYPTO", ib_client, data_layer),
        trigger="cron",
        hour=23,
        minute=45,
        timezone="UTC",
        id="preopen_crypto",
        replace_existing=True,
    )

    scheduler.start()
    logger.info(f"Scheduler started — {SCAN_INTERVAL_MINUTES}min scan, {POSITION_CHECK_MINUTES}min positions")

    bot_thread = threading.Thread(target=start_bot, args=(scheduler,), daemon=True)
    bot_thread.start()
    logger.info("Telegram bot thread started")

    status = "conectado a IB Gateway" if (ib_client and ib_client.ib.isConnected()) else "SIN conexión a IB Gateway"
    notify(
        f"IBKR AI Trader v2 iniciado\n"
        f"Estado IB: {status}\n"
        f"Scanner multi-timeframe: cada {SCAN_INTERVAL_MINUTES} min\n"
        f"Capital cap: ${CAPITAL_CAP}\n"
        f"Circuit breaker: 5% pérdida diaria\n"
        f"Modo: Paper Trading\n"
        f"Dashboard: http://aiutox-pi.tail2a2cda.ts.net:8088/dashboard\n"
        "Escribe /ayuda para ver comandos"
    )

    logger.info("Starting FastAPI on 0.0.0.0:8088...")
    uvicorn.run("app.api.main:app", host="0.0.0.0", port=8088, workers=1)


if __name__ == "__main__":
    main()
