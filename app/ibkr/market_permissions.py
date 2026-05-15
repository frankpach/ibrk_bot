# app/ibkr/market_permissions.py
"""
Consulta IB Gateway para descubrir exchanges y tipos de producto operables.
Resultados cacheados en DB, refrescados diariamente o bajo demanda.
"""
import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

# Contratos de prueba que cubren los principales product types
_PROBE_CONTRACTS = [
    ("STK_US",    "Stock US",        "STK",  "AAPL",    "SMART",    "USD"),
    ("STK_EU",    "Stock Europa",    "STK",  "SAP",     "XETRA",    "EUR"),
    ("STK_HK",    "Stock Hong Kong", "STK",  "0700",    "SEHK",     "HKD"),
    ("OPT_US",    "Options US",      "OPT",  "AAPL",    "SMART",    "USD"),
    ("FUT_US",    "Futuros US",      "FUT",  "ES",      "CME",      "USD"),
    ("CASH_FX",   "Forex",           "CASH", "EUR",     "IDEALPRO", "USD"),
    ("CRYPTO",    "Crypto",          "CRYPTO","BTC",    "PAXOS",    "USD"),
    ("CFD",       "CFD",             "CFD",  "IBUS500", "SMART",    "USD"),
    ("BOND_US",   "Bonos US",        "BOND", "912810RZ7","SMART",   "USD"),
    ("FUND",      "Fondos Mutuos",   "FUND", "VTSMX",   "FUNDSERV", "USD"),
]


async def _probe_contract(ib, sec_type: str, symbol: str, exchange: str, currency: str) -> Optional[dict]:
    """Retorna info del contrato si IB acepta consulta, None si no disponible."""
    try:
        from ib_insync import Contract
        c = Contract(secType=sec_type, symbol=symbol, exchange=exchange, currency=currency)
        details = await ib.reqContractDetailsAsync(c)
        if not details:
            return None
        d = details[0]
        valid_exchanges = getattr(d, "validExchanges", exchange) or exchange
        return {
            "sec_type": sec_type,
            "symbol": symbol,
            "exchange": exchange,
            "currency": currency,
            "valid_exchanges": str(valid_exchanges)[:500],
        }
    except Exception as e:
        logger.debug(f"probe {sec_type}/{symbol}@{exchange}: {e}")
        return None


async def discover_permissions_async(ib) -> list[dict]:
    """
    Prueba cada contrato probe contra IB y retorna los que responden.
    Recibe un ib_insync.IB ya conectado.
    """
    results = []
    for key, label, sec_type, symbol, exchange, currency in _PROBE_CONTRACTS:
        info = await _probe_contract(ib, sec_type, symbol, exchange, currency)
        results.append({
            "key": key,
            "label": label,
            "sec_type": sec_type,
            "available": info is not None,
            "valid_exchanges": info["valid_exchanges"] if info else "",
            "checked_at": datetime.utcnow().isoformat(),
        })
        logger.debug(f"  {label}: {'OK' if info else 'no'}")
    return results


def run_permission_discovery(ib_client) -> list[dict]:
    """
    Punto de entrada sincrónico. Conecta con client_id=98, descubre, desconecta.
    Guarda en DB y retorna la lista.
    """
    from ib_insync import IB
    import asyncio

    async def _run():
        ib = IB()
        try:
            await ib.connectAsync("127.0.0.1", 4002, clientId=98, timeout=15)
            logger.info("market_permissions: connected clientId=98")
            perms = await discover_permissions_async(ib)
        finally:
            ib.disconnect()
        return perms

    try:
        results = asyncio.run(_run())
    except Exception as e:
        logger.error(f"market_permissions discovery failed: {e}")
        return []

    from app.infrastructure.db.compat import upsert_market_permissions
    upsert_market_permissions(results)
    logger.info(f"market_permissions: saved {len(results)} results")
    return results


def get_permissions_report(ib_client=None, force_refresh: bool = False) -> dict:
    """
    Retorna reporte de permisos. Si la cache tiene < 24h usa DB;
    si force_refresh=True o no hay cache, consulta IB.
    """
    from app.infrastructure.db.compat import get_market_permissions, get_market_permissions_age_hours

    age = get_market_permissions_age_hours()
    if force_refresh or age is None or age > 23:
        results = run_permission_discovery(ib_client)
    else:
        results = get_market_permissions()

    available = [r for r in results if r["available"]]
    unavailable = [r for r in results if not r["available"]]
    checked_at = results[0]["checked_at"] if results else None

    return {
        "checked_at": checked_at,
        "cache_age_hours": age,
        "available": available,
        "unavailable": unavailable,
        "total": len(results),
    }
