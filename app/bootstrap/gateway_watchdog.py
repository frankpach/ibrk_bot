# app/bootstrap/gateway_watchdog.py
"""IB Gateway connection monitoring and reconnection logic."""
import logging
import os
import socket
import time

from app.notifications.telegram import notify

logger = logging.getLogger(__name__)

IB_HOST = os.getenv("IB_HOST", "127.0.0.1")
IB_PORT = int(os.getenv("IB_PORT", "4002"))
GATEWAY_CHECK_INTERVAL = 30
GATEWAY_MAX_WAIT = 600


def is_gateway_online() -> bool:
    try:
        with socket.create_connection((IB_HOST, IB_PORT), timeout=3):
            return True
    except (OSError, ConnectionRefusedError):
        return False


def wait_for_gateway() -> bool:
    if is_gateway_online():
        return True
    logger.warning("IB Gateway not available, waiting...")
    notify(
        f"IB Gateway no disponible en el puerto {IB_PORT}.\n"
        "Esperando hasta 10 minutos...\n"
        "Asegúrate de que IB Gateway esté iniciado y con sesión activa."
    )
    elapsed = 0
    while elapsed < GATEWAY_MAX_WAIT:
        time.sleep(GATEWAY_CHECK_INTERVAL)
        elapsed += GATEWAY_CHECK_INTERVAL
        if is_gateway_online():
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
