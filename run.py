# run.py
import logging
import socket
import threading
import time
import uvicorn
from apscheduler.schedulers.background import BackgroundScheduler

from app.db.database import init_db, get_daily_pnl, init_alerts_table, get_active_alerts, mark_alert_triggered, init_market_permissions_table
from app.ibkr.client import get_client
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
from datetime import date

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
        ib_client = get_client()
    except Exception as e:
        logger.error(f"Could not connect to IB Gateway: {e}")
        notify(f"Error conectando a IB Gateway: {e}\nEl sistema iniciará en modo limitado.")
        ib_client = None

    if ib_client:
        logger.info("Reconciling positions...")
        reconcile_positions(ib_client)

    def _run_reconciliation():
        """Wrapper para reconciliar usando el cliente actual (puede haber cambiado)."""
        client = _ib_client_ref.get("client")
        if client:
            try:
                result = reconcile_positions(client)
                logger.info(f"Reconciliation result: {result}")
            except Exception as e:
                logger.error(f"Reconciliation failed: {e}")

    # Create data layer for analysis modules
    from app.analysis.data import IBDataLayer
    data_layer = IBDataLayer(ib_client) if ib_client else None

    scheduler = BackgroundScheduler()
    ctrl = init_controller(scheduler)

    def _check_circuit_breaker():
        daily_pnl = get_daily_pnl()
        client = _ib_client_ref["client"]
        try:
            _acct = client.get_account() if client else {}
            _cap = get_operating_capital(_acct.get("net_liquidation", CAPITAL_CAP))
        except Exception:
            _cap = CAPITAL_CAP
        ctrl.check_circuit_breaker(daily_pnl, _cap)

    def _safe_run_scan():
        client = _ib_client_ref["client"]
        if not client:
            logger.warning("run_scan omitido: sin conexión IB")
            return
        try:
            if not client.ib.isConnected():
                raise ConnectionError("IB desconectado")
            run_scan(client)
        except Exception as e:
            logger.error(f"run_scan falló: {e}")

    # Shared state for reconnection logic
    _ib_client_ref = {"client": ib_client, "data_layer": data_layer}
    _last_connected_at = time.time() if (ib_client and ib_client.ib.isConnected()) else None
    _MISSING_SCAN_JOBS = []  # cola de scans que fallaron por desconexión

    def _check_gateway_and_reconnect():
        """Verifica la conexión a IB Gateway y reconecta si es necesario.
        Si ib_client nunca se creó (arranque sin IB), lo instancia ahora.
        """
        nonlocal _last_connected_at
        client = _ib_client_ref["client"]

        # Caso 1: nunca se conectó al arrancar → intentar crear cliente nuevo
        if client is None:
            if _is_gateway_online():
                logger.info("IB Gateway disponible. Creando IBKRClient por primera vez...")
                try:
                    new_client = get_client()
                    _ib_client_ref["client"] = new_client
                    client = new_client
                    # Crear data_layer si no existe
                    if _ib_client_ref["data_layer"] is None:
                        from app.analysis.data import IBDataLayer
                        _ib_client_ref["data_layer"] = IBDataLayer(new_client)
                        logger.info("IBDataLayer creado")
                    notify("IB Gateway conectado por primera vez. Sistema recuperado.")
                    logger.info("IBKRClient creado exitosamente")
                    _last_connected_at = time.time()
                    # Reconciliar y reintentar scans pendientes
                    reconcile_positions(client)
                    _retry_missed_scans()
                except Exception as e:
                    logger.error(f"No se pudo crear IBKRClient: {e}")
            return
        try:
            if not client.ib.isConnected():
                raise ConnectionError("IB desconectado")
            run_scan(client)
        except Exception as e:
            logger.error(f"run_scan falló: {e}")

    def _check_gateway_and_reconnect():
        """Verifica la conexión a IB Gateway y reconecta si es necesario.
        Si ib_client nunca se creó (arranque sin IB), lo instancia ahora.
        """
        nonlocal _last_connected_at
        client = _ib_client_ref["client"]

        # Caso 1: nunca se conectó al arrancar → intentar crear cliente nuevo
        if client is None:
            if _is_gateway_online():
                logger.info("IB Gateway disponible. Creando IBKRClient por primera vez...")
                try:
                    new_client = IBKRClient()
                    _ib_client_ref["client"] = new_client
                    client = new_client
                    # Crear data_layer si no existe
                    if _ib_client_ref["data_layer"] is None:
                        from app.analysis.data import IBDataLayer
                        _ib_client_ref["data_layer"] = IBDataLayer(new_client)
                        logger.info("IBDataLayer creado")
                    notify("IB Gateway conectado por primera vez. Sistema recuperado.")
                    logger.info("IBKRClient creado exitosamente")
                    _last_connected_at = time.time()
                    # Reconciliar y reintentar scans pendientes
                    reconcile_positions(client)
                    _retry_missed_scans()
                except Exception as e:
                    logger.error(f"No se pudo crear IBKRClient: {e}")
            return

        # Caso 2: cliente existe pero está desconectado
        try:
            is_connected = client.ib.isConnected()
        except Exception:
            is_connected = False

        if not is_connected:
            logger.warning("IB Gateway disconnected, attempting reconnect...")
            try:
                client._run_sync(client._connect_async())
                notify("IB Gateway reconectado automáticamente.")
                logger.info("IB Gateway reconnected")
                _last_connected_at = time.time()
                _retry_missed_scans()
            except Exception as e:
                logger.error(f"Reconnect failed: {e}")
        else:
            _last_connected_at = time.time()

    def _retry_missed_scans():
        """Reintenta scans pre-open que fallaron por desconexión."""
        nonlocal _MISSING_SCAN_JOBS
        if not _MISSING_SCAN_JOBS:
            return
        logger.info(f"Reintentando {_MISSING_SCAN_JOBS} scans fallidos...")
        for job_info in list(_MISSING_SCAN_JOBS):
            market_key, session_date = job_info
            try:
                client = _ib_client_ref["client"]
                dl = _ib_client_ref["data_layer"]
                if client and dl:
                    select_top_symbols(market_key, client, dl, session_date=session_date)
                    _MISSING_SCAN_JOBS.remove(job_info)
                    notify(f"Scan {market_key} reintentado exitosamente.")
            except Exception as e:
                logger.error(f"Reintento de scan {market_key} falló: {e}")

    def _alert_if_long_disconnect():
        """Alerta por Telegram si IB lleva desconectado más de 15 minutos."""
        if _last_connected_at is None:
            return
        elapsed = time.time() - _last_connected_at
        if elapsed > 900 and int(elapsed) % 900 == 0:  # cada 15 min
            minutes = int(elapsed // 60)
            notify(
                f"⚠️ IB Gateway desconectado hace {minutes} minutos.\n"
                "Algunos scans pueden no haberse ejecutado.\n"
                "Usa /diagnostico para revisar."
            )

    def _safe_select_top_symbols(market_key, session_date=None):
        """Wrapper que maneja desconexión y encola para reintento."""
        client = _ib_client_ref["client"]
        dl = _ib_client_ref["data_layer"]
        if not client or not dl:
            logger.warning(f"Pre-open scan {market_key} omitido: sin conexión IB")
            _MISSING_SCAN_JOBS.append((market_key, session_date or date.today().isoformat()))
            notify(
                f"⚠️ Pre-open scan {market_key} NO ejecutado (sin IB Gateway).\n"
                "Se reintentará automáticamente cuando la conexión vuelva."
            )
            return
        try:
            # Verificar conexión activa
            if not client.ib.isConnected():
                raise ConnectionError("IB Gateway desconectado")
            select_top_symbols(market_key, client, dl, session_date=session_date)
        except Exception as e:
            logger.error(f"Pre-open scan {market_key} falló: {e}")
            _MISSING_SCAN_JOBS.append((market_key, session_date or date.today().isoformat()))
            notify(f"⚠️ Pre-open scan {market_key} falló: {e}. Se reintentará.")

    scheduler.add_job(_safe_run_scan, "interval", minutes=SCAN_INTERVAL_MINUTES, id="scanner")
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
            (_ib_client_ref["client"].get_account() if _ib_client_ref["client"] else {}).get("net_liquidation", CAPITAL_CAP)
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
    # Alerta si IB lleva desconectado más de 15 min
    scheduler.add_job(
        _alert_if_long_disconnect,
        "interval",
        minutes=5,
        id="disconnect_alert",
    )
    # Reconciliación periódica cada 10 minutos
    scheduler.add_job(
        _run_reconciliation,
        "interval",
        minutes=10,
        id="reconciler",
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
    def _safe_run_permission_discovery():
        client = _ib_client_ref["client"]
        if not client:
            logger.warning("run_permission_discovery omitido: sin conexión IB")
            return
        try:
            from app.ibkr.market_permissions import run_permission_discovery
            run_permission_discovery(client)
        except Exception as e:
            logger.error(f"run_permission_discovery falló: {e}")

    scheduler.add_job(
        _safe_run_permission_discovery,
        "cron", day_of_week="mon-fri", hour=7, minute=50,
        timezone=MARKET_TZ, id="market_permissions_daily",
    )

    # Pre-open symbol selection jobs (usando wrapper seguro)
    # STK_US: 09:15 ET, Mon-Fri
    scheduler.add_job(
        lambda: _safe_select_top_symbols("STK_US"),
        trigger="cron",
        hour=9,
        minute=15,
        day_of_week="mon-fri",
        timezone=MARKET_TZ,
        id="preopen_stk_us",
        replace_existing=True,
    )

    # FUT_US: 17:45 ET, Sun-Thu (APScheduler: sun=6, mon=0, thu=3)
    scheduler.add_job(
        lambda: _safe_select_top_symbols("FUT_US"),
        trigger="cron",
        hour=17,
        minute=45,
        day_of_week="0-3,6",
        timezone=MARKET_TZ,
        id="preopen_fut_us",
        replace_existing=True,
    )

    # CASH_FX: 16:45 ET, Sun-Thu (APScheduler: sun=6, mon=0, thu=3)
    scheduler.add_job(
        lambda: _safe_select_top_symbols("CASH_FX"),
        trigger="cron",
        hour=16,
        minute=45,
        day_of_week="0-3,6",
        timezone=MARKET_TZ,
        id="preopen_cash_fx",
        replace_existing=True,
    )

    # CRYPTO: 23:45 UTC, daily
    scheduler.add_job(
        lambda: _safe_select_top_symbols("CRYPTO"),
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

    _startup_client = _ib_client_ref["client"]
    status = "conectado a IB Gateway" if (_startup_client and _startup_client.ib.isConnected()) else "SIN conexión a IB Gateway"
    notify(
        f"IBKR AI Trader v2 iniciado\n"
        f"Estado IB: {status}\n"
        f"Scanner multi-timeframe: cada {SCAN_INTERVAL_MINUTES} min\n"
        f"Capital simulado: ${CAPITAL_CAP}\n"
        f"Circuit breaker: 5% pérdida diaria\n"
        f"Modo: Paper Trading (no envia ordenes reales)\n"
        f"Dashboard: http://aiutox-pi.tail2a2cda.ts.net:8088/dashboard\n"
        "Escribe /ayuda para ver comandos"
    )

    logger.info("Starting FastAPI on 0.0.0.0:8088...")
    uvicorn.run("app.api.main:app", host="0.0.0.0", port=8088, workers=1)


if __name__ == "__main__":
    main()
