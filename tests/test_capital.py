# tests/test_capital.py
"""Tests para logica de capital operativo dinamico desde IB."""
import pytest
from app.api.capital import get_operating_capital


def test_capital_uses_real_when_below_cap():
    assert get_operating_capital(400.0) == 400.0


def test_capital_uses_cap_when_account_is_larger():
    assert get_operating_capital(1_031_314.0) == 500.0


def test_capital_uses_real_in_live_mode(monkeypatch):
    import app.config.settings as s
    monkeypatch.setattr(s, "CAPITAL_CAP", 10_000.0)
    from app.api import capital as cap_mod
    monkeypatch.setattr(cap_mod, "CAPITAL_CAP", 10_000.0)
    assert get_operating_capital(800.0) == 800.0


def test_capital_exact_cap():
    assert get_operating_capital(500.0) == 500.0
