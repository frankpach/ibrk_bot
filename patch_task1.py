#!/usr/bin/env python3
"""Patch script for Task 1: replace SIMULATED_CAPITAL with dynamic capital."""
import pathlib

BASE = pathlib.Path("/home/frankpach/ibkr-bot")

# ── 1. settings.py ──────────────────────────────────────────────────────────
settings_path = BASE / "app/config/settings.py"
settings_text = settings_path.read_text()
settings_text = settings_text.replace(
    "SIMULATED_CAPITAL = 500.0",
    'CAPITAL_CAP = float(os.getenv("CAPITAL_CAP", "500.0"))'
)
settings_path.write_text(settings_text)
print("✓ settings.py patched")

# ── 2. app/api/capital.py (new file) ────────────────────────────────────────
capital_path = BASE / "app/api/capital.py"
capital_path.write_text(
    '# app/api/capital.py\n'
    '"""Fuente unica de verdad para el capital operativo del sistema."""\n'
    'from app.config.settings import CAPITAL_CAP\n'
    '\n'
    '\n'
    'def get_operating_capital(ib_net_liquidation: float) -> float:\n'
    '    """\n'
    '    Capital operativo = min(saldo real IB, CAPITAL_CAP).\n'
    '    Nunca usa un valor fijo inventado -- siempre parte del saldo real.\n'
    '    """\n'
    '    return min(ib_net_liquidation, CAPITAL_CAP)\n'
)
print("✓ app/api/capital.py created")

# ── 3. tests/test_capital.py (new file) ────────────────────────────────────
test_capital_path = BASE / "tests/test_capital.py"
test_capital_path.write_text(
    '# tests/test_capital.py\n'
    '"""Tests para logica de capital operativo dinamico desde IB."""\n'
    'import pytest\n'
    'from app.api.capital import get_operating_capital\n'
    '\n'
    '\n'
    'def test_capital_uses_real_when_below_cap():\n'
    '    assert get_operating_capital(400.0) == 400.0\n'
    '\n'
    '\n'
    'def test_capital_uses_cap_when_account_is_larger():\n'
    '    assert get_operating_capital(1_031_314.0) == 500.0\n'
    '\n'
    '\n'
    'def test_capital_uses_real_in_live_mode(monkeypatch):\n'
    '    import app.config.settings as s\n'
    '    monkeypatch.setattr(s, "CAPITAL_CAP", 10_000.0)\n'
    '    from app.api import capital as cap_mod\n'
    '    monkeypatch.setattr(cap_mod, "CAPITAL_CAP", 10_000.0)\n'
    '    assert get_operating_capital(800.0) == 800.0\n'
    '\n'
    '\n'
    'def test_capital_exact_cap():\n'
    '    assert get_operating_capital(500.0) == 500.0\n'
)
print("✓ tests/test_capital.py created")

# ── 4. app/api/main.py ──────────────────────────────────────────────────────
main_path = BASE / "app/api/main.py"
main_text = main_path.read_text()

# Fix top-level import line (line 6)
main_text = main_text.replace(
    "from app.config.settings import ALLOWED_SYMBOLS, MARKET_TZ, MAX_RISK_PCT, MIN_RISK_USD, MAX_POSITION_USD, SIMULATED_CAPITAL",
    "from app.config.settings import ALLOWED_SYMBOLS, MARKET_TZ, MAX_RISK_PCT, MIN_RISK_USD, MAX_POSITION_USD\n"
    "from app.api.capital import get_operating_capital"
)

# Fix /orders/preview (line ~105): account is already fetched, use net_liquidation
main_text = main_text.replace(
    "        account = client.get_account()\n"
    "        capital = SIMULATED_CAPITAL  # usa capital simulado de $500, no el real de IB paper\n"
    "    except Exception as exc:\n"
    "        raise HTTPException(status_code=500, detail=f\"Could not fetch account: {exc}\")\n"
    "    try:\n"
    "        portfolio = client.get_portfolio()\n"
    "        active_positions = len(portfolio)\n"
    "    except Exception as exc:\n"
    "        raise HTTPException(status_code=500, detail=f\"Could not fetch portfolio: {exc}\")\n"
    "\n"
    "    result = validate_order(\n"
    "        symbol=symbol, action=req.action, quantity=req.quantity,",
    "        account = client.get_account()\n"
    "        capital = get_operating_capital(account.get(\"net_liquidation\", 0.0))\n"
    "    except Exception as exc:\n"
    "        raise HTTPException(status_code=500, detail=f\"Could not fetch account: {exc}\")\n"
    "    try:\n"
    "        portfolio = client.get_portfolio()\n"
    "        active_positions = len(portfolio)\n"
    "    except Exception as exc:\n"
    "        raise HTTPException(status_code=500, detail=f\"Could not fetch portfolio: {exc}\")\n"
    "\n"
    "    result = validate_order(\n"
    "        symbol=symbol, action=req.action, quantity=req.quantity,"
)

# Fix /system/status endpoint (lines ~290-303)
main_text = main_text.replace(
    "    from app.config.settings import SIMULATED_CAPITAL\n"
    "    try:\n"
    "        ctrl = get_controller()\n"
    "        status = ctrl.status()\n"
    "    except RuntimeError:\n"
    "        status = {\"paused\": False, \"mode\": \"paper\", \"circuit_breaker_threshold\": \"5%\"}\n"
    "    open_trades = get_open_trades()\n"
    "    daily_pnl = get_daily_pnl()\n"
    "    return {\n"
    "        **status,\n"
    "        \"open_positions\": len(open_trades),\n"
    "        \"daily_pnl_usd\": round(daily_pnl, 2),\n"
    "        \"daily_pnl_pct\": round(daily_pnl / SIMULATED_CAPITAL * 100, 2),\n"
    "        \"simulated_capital\": SIMULATED_CAPITAL,\n"
    "    }",
    "    try:\n"
    "        ctrl = get_controller()\n"
    "        status = ctrl.status()\n"
    "    except RuntimeError:\n"
    "        status = {\"paused\": False, \"mode\": \"paper\", \"circuit_breaker_threshold\": \"5%\"}\n"
    "    open_trades = get_open_trades()\n"
    "    daily_pnl = get_daily_pnl()\n"
    "    try:\n"
    "        _acct = client.get_account()\n"
    "        _capital = get_operating_capital(_acct.get(\"net_liquidation\", 0.0))\n"
    "    except Exception:\n"
    "        from app.config.settings import CAPITAL_CAP\n"
    "        _capital = CAPITAL_CAP\n"
    "    return {\n"
    "        **status,\n"
    "        \"open_positions\": len(open_trades),\n"
    "        \"daily_pnl_usd\": round(daily_pnl, 2),\n"
    "        \"daily_pnl_pct\": round(daily_pnl / _capital * 100, 2) if _capital else 0.0,\n"
    "        \"operating_capital\": _capital,\n"
    "    }"
)

# Fix /dashboard endpoint (lines ~406-417)
main_text = main_text.replace(
    "    from app.config.settings import SIMULATED_CAPITAL, ALLOWED_SYMBOLS\n"
    "\n"
    "    daily_pnl = get_daily_pnl()\n"
    "    open_trades = get_open_trades()\n"
    "\n"
    "    status_data = {\n"
    "        \"mode\": \"paper\",\n"
    "        \"paused\": False,\n"
    "        \"daily_pnl_usd\": round(daily_pnl, 2),\n"
    "        \"daily_pnl_pct\": round(daily_pnl / SIMULATED_CAPITAL * 100, 2),\n"
    "        \"open_positions\": len(open_trades),\n"
    "        \"simulated_capital\": SIMULATED_CAPITAL,\n"
    "    }",
    "    from app.config.settings import ALLOWED_SYMBOLS\n"
    "\n"
    "    daily_pnl = get_daily_pnl()\n"
    "    open_trades = get_open_trades()\n"
    "    try:\n"
    "        _acct = client.get_account()\n"
    "        _capital = get_operating_capital(_acct.get(\"net_liquidation\", 0.0))\n"
    "    except Exception:\n"
    "        from app.config.settings import CAPITAL_CAP\n"
    "        _capital = CAPITAL_CAP\n"
    "\n"
    "    status_data = {\n"
    "        \"mode\": \"paper\",\n"
    "        \"paused\": False,\n"
    "        \"daily_pnl_usd\": round(daily_pnl, 2),\n"
    "        \"daily_pnl_pct\": round(daily_pnl / _capital * 100, 2) if _capital else 0.0,\n"
    "        \"open_positions\": len(open_trades),\n"
    "        \"operating_capital\": _capital,\n"
    "    }"
)

# Fix /backtest/{symbol} endpoint (lines ~467-476)
main_text = main_text.replace(
    "    from app.config.settings import SIMULATED_CAPITAL\n"
    "    symbol = symbol.upper()\n"
    "    if symbol not in ALLOWED_SYMBOLS:\n"
    "        raise HTTPException(status_code=403, detail=f\"Symbol {symbol} not in allowed list\")\n"
    "    try:\n"
    "        result = run_backtest(\n"
    "            symbol=symbol,\n"
    "            ib_client=client,\n"
    "            period_days=days,\n"
    "            capital=SIMULATED_CAPITAL,\n"
    "        )",
    "    symbol = symbol.upper()\n"
    "    if symbol not in ALLOWED_SYMBOLS:\n"
    "        raise HTTPException(status_code=403, detail=f\"Symbol {symbol} not in allowed list\")\n"
    "    try:\n"
    "        _acct = client.get_account()\n"
    "        _capital = get_operating_capital(_acct.get(\"net_liquidation\", 0.0))\n"
    "    except Exception:\n"
    "        from app.config.settings import CAPITAL_CAP\n"
    "        _capital = CAPITAL_CAP\n"
    "    try:\n"
    "        result = run_backtest(\n"
    "            symbol=symbol,\n"
    "            ib_client=client,\n"
    "            period_days=days,\n"
    "            capital=_capital,\n"
    "        )"
)

main_path.write_text(main_text)
print("✓ app/api/main.py patched")

# ── 5. run.py ────────────────────────────────────────────────────────────────
run_path = BASE / "run.py"
run_text = run_path.read_text()

# Fix import line
run_text = run_text.replace(
    "from app.config.settings import SCAN_INTERVAL_MINUTES, POSITION_CHECK_MINUTES, SIMULATED_CAPITAL, MARKET_TZ",
    "from app.config.settings import SCAN_INTERVAL_MINUTES, POSITION_CHECK_MINUTES, CAPITAL_CAP, MARKET_TZ\n"
    "from app.api.capital import get_operating_capital"
)

# Fix _check_circuit_breaker
run_text = run_text.replace(
    "    def _check_circuit_breaker():\n"
    "        daily_pnl = get_daily_pnl()\n"
    "        ctrl.check_circuit_breaker(daily_pnl, SIMULATED_CAPITAL)",
    "    def _check_circuit_breaker():\n"
    "        daily_pnl = get_daily_pnl()\n"
    "        try:\n"
    "            _acct = ib_client.get_account() if ib_client else {}\n"
    "            _cap = get_operating_capital(_acct.get(\"net_liquidation\", CAPITAL_CAP))\n"
    "        except Exception:\n"
    "            _cap = CAPITAL_CAP\n"
    "        ctrl.check_circuit_breaker(daily_pnl, _cap)"
)

# Fix send_weekly_report lambda
run_text = run_text.replace(
    "        lambda: send_weekly_report(SIMULATED_CAPITAL),",
    "        lambda: send_weekly_report(get_operating_capital(\n"
    "            (ib_client.get_account() if ib_client else {}).get(\"net_liquidation\", CAPITAL_CAP)\n"
    "        )),"
)

# Fix startup notification
run_text = run_text.replace(
    '        f"Capital simulado: ${SIMULATED_CAPITAL}\\n"',
    '        f"Capital cap: ${CAPITAL_CAP}\\n"'
)

run_path.write_text(run_text)
print("✓ run.py patched")

# ── Verify no SIMULATED_CAPITAL remains ─────────────────────────────────────
for fpath in [settings_path, main_path, run_path, capital_path, test_capital_path]:
    text = fpath.read_text()
    if "SIMULATED_CAPITAL" in text:
        print(f"ERROR: SIMULATED_CAPITAL still in {fpath}")
    else:
        print(f"  OK: no SIMULATED_CAPITAL in {fpath.name}")

print("\nAll patches applied.")
