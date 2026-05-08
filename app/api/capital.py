# app/api/capital.py
"""Fuente unica de verdad para el capital operativo del sistema."""
from app.config.settings import CAPITAL_CAP


def get_operating_capital(ib_net_liquidation: float) -> float:
    """
    Capital operativo = min(saldo real IB, CAPITAL_CAP).
    Nunca usa un valor fijo inventado -- siempre parte del saldo real.
    """
    return min(ib_net_liquidation, CAPITAL_CAP)
