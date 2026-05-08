"""Contract factory: turns (symbol, sec_type, exchange, currency) tuples into
ib_insync Contract objects. Single source of truth for multi-market support.
"""
from __future__ import annotations

import re
from ib_insync import Contract, Forex, Future, Option, Stock


class ContractFactoryError(Exception):
    """Base class for contract-factory errors."""


class UnsupportedSecTypeError(ContractFactoryError):
    """Raised when sec_type is not one of STK / OPT / FUT / CASH / CRYPTO."""


class InvalidForexPairError(ContractFactoryError):
    """Raised when a CASH symbol is not a valid 6-letter currency pair."""


_FOREX_RE = re.compile(r"^[A-Z]{3}[A-Z]{3}$")


def parse_forex_pair(pair: str) -> tuple[str, str]:
    """Split 'EURUSD' -> ('EUR', 'USD'). Case-insensitive. Raises on invalid."""
    if not isinstance(pair, str):
        raise InvalidForexPairError(f"Forex pair must be str, got {type(pair)!r}")
    p = pair.upper()
    if not _FOREX_RE.match(p):
        raise InvalidForexPairError(
            f"Invalid forex pair {pair!r}: expected 6 letters like 'EURUSD'"
        )
    return p[:3], p[3:]


def build_contract(
    symbol: str,
    sec_type: str,
    exchange: str,
    currency: str,
) -> Contract:
    """Build the ib_insync Contract for the given metadata.

    For FUT, the returned contract has no lastTradeDateOrContractMonth set;
    the caller is responsible for resolving the front-month via
    IB.reqContractDetailsAsync(...) and using the qualified contract.
    """
    sym = symbol.upper().strip()
    sec = sec_type.upper().strip()

    if sec == "STK":
        return Stock(sym, exchange or "SMART", currency or "USD")

    if sec == "OPT":
        return Option(sym, "", 0.0, "C", exchange or "SMART", currency=currency or "USD")

    if sec == "FUT":
        return Future(symbol=sym, exchange=exchange or "CME", currency=currency or "USD")

    if sec == "CASH":
        base, quote = parse_forex_pair(sym)
        c = Forex(pair=f"{base}{quote}")
        c.exchange = exchange or "IDEALPRO"
        return c

    if sec == "CRYPTO":
        return Contract(
            secType="CRYPTO",
            symbol=sym,
            exchange=exchange or "PAXOS",
            currency=currency or "USD",
        )

    raise UnsupportedSecTypeError(
        f"sec_type={sec_type!r} is not supported. "
        "Expected one of: STK, OPT, FUT, CASH, CRYPTO"
    )


def get_what_to_show(sec_type: str) -> str:
    """Historical-data whatToShow value per asset class.

    Forex has no trade prints - IB requires MIDPOINT (or BID/ASK) for CASH.
    Everything else uses TRADES.
    """
    return "MIDPOINT" if sec_type.upper() == "CASH" else "TRADES"


def get_use_rth(sec_type: str) -> bool:
    """useRTH=True only for equities/options. FUT/CASH/CRYPTO trade ~24h."""
    return sec_type.upper() in {"STK", "OPT"}


__all__ = [
    "build_contract",
    "get_what_to_show",
    "get_use_rth",
    "parse_forex_pair",
    "ContractFactoryError",
    "UnsupportedSecTypeError",
    "InvalidForexPairError",
]
