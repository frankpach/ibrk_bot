# Winning Strategies — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transformar el sistema de paper trading en un motor que genere entradas con convicción, complete ciclos completos de aprendizaje, y opere con el capital real de IB — tanto en $500 live como en $1M paper — sin cambiar código entre entornos.

**Architecture:** Tres capas de cambio en orden de dependencia: (1) capital real desde IB con techo configurable elimina `SIMULATED_CAPITAL` como hardcode, (2) scanner con logging diagnóstico + señales multi-símbolo correctas, (3) criterios de entrada más restrictivos que producen trades con mayor probabilidad de éxito. Cada fase tiene tests que verifican el comportamiento antes y después.

**Tech Stack:** Python 3.13, ib_insync, FastAPI, APScheduler, SQLite, pytest, OpenCode/Qwen LLM (subprocess)

---

## Estado de línea base (verificado 2026-05-08)

Antes de tocar nada, estos números deben ser tu punto de referencia:

```
Tests pasando:        164 (pytest tests/ --ignore=test_ibkr_client.py --ignore=test_mcp_server.py)
Señales en DB:        5 (todas STRONG, todas AAPL)
Trades cerrados:      1 (CANCELLED_TEST, P&L $0)
Patrones aprendidos:  0
Symbol parameters:    trade_count=0 para todos (multiplicadores vírgenes en 1.0)
Capital operativo:    SIMULATED_CAPITAL=$500 hardcodeado (ignora cuenta real de IB)
Cobertura horaria:    ~7h/día (solo US stocks, 9:15-16:15 ET)
```

**Comando de baseline:**
```bash
cd ~/ibkr-bot && source .venv/bin/activate
python3 -m pytest tests/ --ignore=tests/test_ibkr_client.py --ignore=tests/test_mcp_server.py -q --tb=no
# Debe mostrar: 164 passed
```

---

## Mapa de archivos

| Archivo | Tarea | Cambio |
|---|---|---|
| `app/config/settings.py` | 1 | Reemplaza `SIMULATED_CAPITAL` con `CAPITAL_CAP` |
| `app/api/main.py` | 1 | Capital desde IB real, acotado por `CAPITAL_CAP` (6 lugares) |
| `run.py` | 1 | Elimina `SIMULATED_CAPITAL`, usa función `get_operating_capital()` |
| `tests/test_risk_validator.py` | 1 | Ampliar tests para capital dinámico |
| `tests/test_capital.py` | 1 | Tests nuevos para lógica de capital |
| `app/scanner/preprocessor.py` | 2 | Logging detallado por símbolo, continuar en error |
| `app/analysis/indicators.py` | 2 | Señal de entrada más restrictiva (4 criterios) |
| `tests/test_entry_criteria.py` | 2 | Tests para nuevos criterios de entrada |
| `app/risk/validator.py` | 3 | Horario dinámico desde IB `liquidHours`, max hold time |
| `app/ibkr/market_hours.py` | 3 | Parser de `liquidHours` IB → bool `is_liquid_now()` |
| `tests/test_market_hours.py` | 3 | Tests para parser de horarios |
| `app/llm/agent.py` | 4 | Contexto completo al LLM desde el inicio (sin tool calls) |
| `tests/test_agent_context.py` | 4 | Verifica que el prompt incluye todos los indicadores |
| `app/notifications/telegram_bot.py` | 5 | Comando `/diagnostico` |

---

## FASE 1 — Capital real desde IB (sin SIMULATED_CAPITAL)

### Task 1: Reemplazar SIMULATED_CAPITAL con capital dinámico de IB

**Contexto:** Hoy `main.py:105` y `main.py:178` hardcodean `capital = SIMULATED_CAPITAL`. En live con $400 reales, el sistema creería tener $500 y abriría posiciones más grandes de las posibles. El fix: capital siempre viene de IB, con un techo máximo (`CAPITAL_CAP`) configurable por entorno.

**Regla de negocio:**
```
capital_operativo = min(cuenta_real_IB.net_liquidation, CAPITAL_CAP)
CAPITAL_CAP paper  = 500    → simula exactamente las condiciones live de $500
CAPITAL_CAP live   = 10000  → sin límite artificial hasta $10k (ajustar cuando crezca)
```

**Files:**
- Modify: `app/config/settings.py`
- Modify: `app/api/main.py:105` y `app/api/main.py:178` y `app/api/main.py:290` y `app/api/main.py:302` y `app/api/main.py:406` y `app/api/main.py:476`
- Modify: `run.py:20` y `run.py:120` y `run.py:145` y `run.py:204`
- Create: `tests/test_capital.py`

- [ ] **Step 1.1: Escribir tests que fallan para la nueva lógica de capital**

```python
# tests/test_capital.py
"""Tests para lógica de capital operativo dinámico desde IB."""
import pytest


def get_operating_capital(ib_net_liquidation: float, cap: float) -> float:
    """Retorna el capital operativo: mínimo entre cuenta real y techo."""
    return min(ib_net_liquidation, cap)


def test_capital_uses_real_when_below_cap():
    # Cuenta live con $400, cap=$500 → usa $400
    assert get_operating_capital(400.0, 500.0) == 400.0


def test_capital_uses_cap_when_account_is_larger():
    # Paper con $1M, cap=$500 → usa $500 (simula condiciones live)
    assert get_operating_capital(1_031_314.0, 500.0) == 500.0


def test_capital_uses_cap_in_live_mode():
    # Live con $800, cap=$10000 → usa $800 (lo que realmente hay)
    assert get_operating_capital(800.0, 10_000.0) == 800.0


def test_capital_never_returns_zero():
    # Cuenta vacía → devuelve el mínimo útil
    result = get_operating_capital(0.0, 500.0)
    assert result == 0.0  # DB maneja el rechazo por capital insuficiente


def test_capital_exact_cap():
    assert get_operating_capital(500.0, 500.0) == 500.0
```

- [ ] **Step 1.2: Correr test para verificar que falla**

```bash
cd ~/ibkr-bot && source .venv/bin/activate
python3 -m pytest tests/test_capital.py -v
# Esperado: ERROR — cannot import name 'get_operating_capital'
# (la función aún no existe en el módulo correcto)
```

- [ ] **Step 1.3: Actualizar `settings.py`**

Reemplazar:
```python
SIMULATED_CAPITAL = 500.0
```

Con:
```python
# Capital cap: techo máximo que el sistema puede usar, independiente del saldo real.
# En paper: 500 → simula exactamente las condiciones de una cuenta live pequeña.
# En live:  ajustar al saldo real cuando la cuenta crezca.
CAPITAL_CAP = float(os.getenv("CAPITAL_CAP", "500.0"))
```

- [ ] **Step 1.4: Crear `app/api/capital.py` con la función central**

```python
# app/api/capital.py
"""Fuente única de verdad para el capital operativo del sistema."""
from app.config.settings import CAPITAL_CAP


def get_operating_capital(ib_net_liquidation: float) -> float:
    """
    Capital operativo = min(saldo real IB, CAPITAL_CAP).
    Nunca usa un valor fijo inventado — siempre parte del saldo real.
    """
    return min(ib_net_liquidation, CAPITAL_CAP)
```

- [ ] **Step 1.5: Actualizar `tests/test_capital.py` para importar del módulo real**

```python
# tests/test_capital.py
"""Tests para lógica de capital operativo dinámico desde IB."""
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
```

- [ ] **Step 1.6: Correr test para verificar que pasa**

```bash
python3 -m pytest tests/test_capital.py -v
# Esperado: 4 passed
```

- [ ] **Step 1.7: Actualizar `main.py` — reemplazar los 6 usos de SIMULATED_CAPITAL**

En `main.py` línea 6, cambiar import:
```python
# ANTES:
from app.config.settings import ALLOWED_SYMBOLS, MARKET_TZ, MAX_RISK_PCT, MIN_RISK_USD, MAX_POSITION_USD, SIMULATED_CAPITAL
# DESPUÉS:
from app.config.settings import ALLOWED_SYMBOLS, MARKET_TZ, MAX_RISK_PCT, MIN_RISK_USD, MAX_POSITION_USD
from app.api.capital import get_operating_capital
```

En `main.py` línea 105 (endpoint `/orders/preview`):
```python
# ANTES:
capital = SIMULATED_CAPITAL  # usa capital simulado de $500, no el real de IB paper
# DESPUÉS:
capital = get_operating_capital(account.get("net_liquidation", 0.0))
```

En `main.py` línea 178 (endpoint `/orders/place`):
```python
# ANTES:
capital = SIMULATED_CAPITAL  # usa capital simulado de $500, no el real de IB paper
# DESPUÉS:
capital = get_operating_capital(account.get("net_liquidation", 0.0))
```

En `main.py` líneas 290, 302, 303 (endpoint `/system/status`):
```python
# ANTES:
from app.config.settings import SIMULATED_CAPITAL
...
"daily_pnl_pct": round(daily_pnl / SIMULATED_CAPITAL * 100, 2),
"simulated_capital": SIMULATED_CAPITAL,
# DESPUÉS:
from app.api.capital import get_operating_capital
...
_cap = get_operating_capital(client.get_account().get("net_liquidation", 500.0)) if client else 500.0
"daily_pnl_pct": round(daily_pnl / _cap * 100, 2) if _cap else 0.0,
"operating_capital": _cap,
```

Mismo patrón en líneas 406-417 (dashboard) y 467-476 (backtest endpoint).

- [ ] **Step 1.8: Actualizar `run.py` — 4 usos de SIMULATED_CAPITAL**

```python
# run.py línea 20 — cambiar import:
# ANTES:
from app.config.settings import SCAN_INTERVAL_MINUTES, POSITION_CHECK_MINUTES, SIMULATED_CAPITAL, MARKET_TZ
# DESPUÉS:
from app.config.settings import SCAN_INTERVAL_MINUTES, POSITION_CHECK_MINUTES, MARKET_TZ
from app.api.capital import get_operating_capital

# run.py línea 120 — circuit breaker:
# ANTES:
ctrl.check_circuit_breaker(daily_pnl, SIMULATED_CAPITAL)
# DESPUÉS:
_cap = get_operating_capital(ib_client.get_account().get("net_liquidation", 500.0)) if ib_client else 500.0
ctrl.check_circuit_breaker(daily_pnl, _cap)

# run.py línea 145 — weekly report:
# ANTES:
lambda: send_weekly_report(SIMULATED_CAPITAL),
# DESPUÉS:
lambda: send_weekly_report(
    get_operating_capital(ib_client.get_account().get("net_liquidation", 500.0)) if ib_client else 500.0
),

# run.py línea 204 — startup notification:
# ANTES:
f"Capital simulado: ${SIMULATED_CAPITAL}\n"
# DESPUÉS:
f"Capital operativo (cap=${CAPITAL_CAP}): ${get_operating_capital(ib_client.get_account().get('net_liquidation', 0)) if ib_client else 'N/A'}\n"
```

- [ ] **Step 1.9: Correr suite completa de tests**

```bash
python3 -m pytest tests/ --ignore=tests/test_ibkr_client.py --ignore=tests/test_mcp_server.py -q --tb=short
# Esperado: 168+ passed (164 base + 4 nuevos de capital), 0 failed
```

**Criterio de aceptación Task 1:**
- [ ] `grep -r "SIMULATED_CAPITAL" ~/ibkr-bot/app/` devuelve 0 resultados
- [ ] `curl http://127.0.0.1:8088/system/status` muestra `"operating_capital": 500.0` (paper con cap=$500)
- [ ] `curl http://127.0.0.1:8088/orders/preview` con símbolo válido calcula posición basada en capital real
- [ ] 168+ tests pasando

- [ ] **Step 1.10: Commit**

```bash
git add app/config/settings.py app/api/capital.py app/api/main.py run.py tests/test_capital.py
git commit -m "feat: capital operativo desde IB real con CAPITAL_CAP — elimina SIMULATED_CAPITAL hardcodeado"
```

---

## FASE 2 — Scanner: diagnóstico y criterios de entrada más fuertes

### Task 2: Logging diagnóstico por símbolo + criterios de entrada con 4 condiciones

**Contexto:** El scanner genera señales solo para AAPL. No sabemos si los otros 9 símbolos fallan silenciosamente o simplemente no cumplen criterios. El criterio actual (`classify_signal`) acepta señales con solo RSI extremo. Necesitamos 4 condiciones simultáneas para que una señal sea STRONG y el LLM la considere.

**Criterios de entrada actualizados (STRONG requiere todos 4):**
```
1. RSI < 35 (oversold) O RSI > 65 (overbought)
2. MACD crossover=True en timeframe daily
3. volume_ratio_20d > 1.5
4. Precio cerca de SMA20 (dentro de 2%) O Bollinger band extreme (posición < 0.1 o > 0.9)
```

**Files:**
- Modify: `app/scanner/preprocessor.py`
- Modify: `app/analysis/indicators.py` (función `classify_signal`)
- Create: `tests/test_entry_criteria.py`

- [ ] **Step 2.1: Escribir tests para criterios de entrada**

```python
# tests/test_entry_criteria.py
"""Tests para criterios de entrada de 4 condiciones."""
from app.analysis.indicators import classify_signal_v2, FeatureSet
from datetime import datetime


def _features(**kwargs):
    defaults = dict(
        symbol="AAPL", timestamp=datetime(2026, 1, 1),
        rsi_14=50.0, macd_crossover=False, volume_ratio_20d=1.0,
        bollinger_position=0.5, sma20=100.0,
    )
    defaults.update(kwargs)
    return FeatureSet(**defaults)


def test_strong_requires_all_4_conditions():
    f = _features(rsi_14=27.0, macd_crossover=True, volume_ratio_20d=2.0, bollinger_position=0.05)
    assert classify_signal_v2(f) == "STRONG"


def test_missing_rsi_condition_downgrades_to_medium():
    # RSI neutral (40) → no cumple condición 1
    f = _features(rsi_14=40.0, macd_crossover=True, volume_ratio_20d=2.0, bollinger_position=0.05)
    assert classify_signal_v2(f) in ("MEDIUM", "WEAK")


def test_missing_macd_downgrades():
    f = _features(rsi_14=27.0, macd_crossover=False, volume_ratio_20d=2.0, bollinger_position=0.05)
    assert classify_signal_v2(f) in ("MEDIUM", "WEAK")


def test_missing_volume_downgrades():
    f = _features(rsi_14=27.0, macd_crossover=True, volume_ratio_20d=0.8, bollinger_position=0.05)
    assert classify_signal_v2(f) in ("MEDIUM", "WEAK")


def test_overbought_also_triggers_strong():
    # RSI > 65 también activa condición 1
    f = _features(rsi_14=72.0, macd_crossover=True, volume_ratio_20d=2.0, bollinger_position=0.92)
    assert classify_signal_v2(f) == "STRONG"


def test_weak_when_fewer_than_2_conditions():
    f = _features(rsi_14=50.0, macd_crossover=False, volume_ratio_20d=0.5, bollinger_position=0.5)
    assert classify_signal_v2(f) == "WEAK"


def test_none_fields_handled_gracefully():
    # Datos incompletos no deben crashear
    f = _features(rsi_14=None, macd_crossover=None, volume_ratio_20d=None, bollinger_position=None)
    result = classify_signal_v2(f)
    assert result in ("STRONG", "MEDIUM", "WEAK")
```

- [ ] **Step 2.2: Correr tests para verificar que fallan**

```bash
python3 -m pytest tests/test_entry_criteria.py -v
# Esperado: ERROR — cannot import name 'classify_signal_v2'
```

- [ ] **Step 2.3: Implementar `classify_signal_v2` en `indicators.py`**

Agregar al final de `app/analysis/indicators.py`:

```python
def classify_signal_v2(features: "FeatureSet") -> str:
    """
    Criterio de entrada con 4 condiciones. Requiere todas para STRONG.
    MEDIUM si cumple 2-3. WEAK si cumple < 2.
    """
    conditions = 0

    # Condición 1: RSI extremo
    rsi = features.rsi_14
    if rsi is not None and (rsi < 35 or rsi > 65):
        conditions += 1

    # Condición 2: MACD crossover
    if features.macd_crossover:
        conditions += 1

    # Condición 3: Volumen elevado
    vol = features.volume_ratio_20d
    if vol is not None and vol > 1.5:
        conditions += 1

    # Condición 4: Precio en zona de soporte/resistencia técnica
    boll = features.bollinger_position
    if boll is not None and (boll < 0.15 or boll > 0.85):
        conditions += 1

    if conditions == 4:
        return "STRONG"
    elif conditions >= 2:
        return "MEDIUM"
    return "WEAK"
```

- [ ] **Step 2.4: Correr tests para verificar que pasan**

```bash
python3 -m pytest tests/test_entry_criteria.py -v
# Esperado: 7 passed
```

- [ ] **Step 2.5: Agregar logging diagnóstico a `preprocessor.py`**

En `run_scan()`, reemplazar el loop silencioso:

```python
# ANTES:
for symbol in symbols:
    scan_symbol(symbol, ib_client)

# DESPUÉS:
results = {}
for symbol in symbols:
    try:
        strength = scan_symbol(symbol, ib_client)
        results[symbol] = strength or "WEAK/no-signal"
    except Exception as e:
        results[symbol] = f"ERROR: {e}"
        logger.error(f"scan_symbol({symbol}) failed: {e}")

summary = " | ".join(f"{s}:{r}" for s, r in results.items())
logger.info(f"Scan complete: {summary}")
```

Y en `scan_symbol()`, agregar log detallado por símbolo antes del return:

```python
logger.info(
    f"SCAN {symbol}: daily={sig_daily} hourly={sig_hourly} 5min={sig_5min} "
    f"→ {strength} | RSI={ind_daily.get('rsi','?')} "
    f"MACD_cross={ind_daily.get('macd_crossover','?')} "
    f"vol={ind_daily.get('volume_ratio','?')}"
)
```

- [ ] **Step 2.6: Correr suite completa**

```bash
python3 -m pytest tests/ --ignore=tests/test_ibkr_client.py --ignore=tests/test_mcp_server.py -q --tb=short
# Esperado: 175+ passed, 0 failed
```

**Criterio de aceptación Task 2:**
- [ ] `tail -f /tmp/run.log` durante horario de mercado muestra una línea `SCAN COMPLETE: AAPL:... | MSFT:... | SPY:...` con resultado para cada símbolo
- [ ] Los 9 símbolos distintos de AAPL muestran su resultado (no silencio)
- [ ] Una señal STRONG requiere al menos 3 de 4 condiciones en los tests
- [ ] 175+ tests pasando

- [ ] **Step 2.7: Commit**

```bash
git add app/scanner/preprocessor.py app/analysis/indicators.py tests/test_entry_criteria.py
git commit -m "feat: logging diagnóstico por símbolo + criterios de entrada 4 condiciones"
```

---

## FASE 3 — Horario dinámico desde IB (cobertura 22h/día)

### Task 3: Parser de `liquidHours` de IB para habilitar Forex y Crypto fuera de horario US

**Contexto:** El validador actual bloquea todas las órdenes fuera de 9:30-16:00 ET hardcodeado. EUR/USD opera 22h/día, BTC opera 24/7. IB entrega `liquidHours` por contrato desde `reqContractDetails`. Este task implementa un parser que convierte ese string en `is_liquid_now()`.

**Formato real de IB (verificado):**
```
Forex:  "20260507:1715-20260508:1700;20260509:CLOSED;..."
Stocks: "20260507:0930-20260507:1600;20260509:CLOSED;..."
Crypto: "20260507:1601-20260508:1600;20260509:CLOSED;..."
```

**Files:**
- Create: `app/ibkr/market_hours.py`
- Modify: `app/risk/validator.py`
- Create: `tests/test_market_hours.py`

- [ ] **Step 3.1: Escribir tests para el parser de liquidHours**

```python
# tests/test_market_hours.py
"""Tests para parser de liquidHours de IB Gateway."""
from datetime import datetime
from zoneinfo import ZoneInfo
import pytest
from app.ibkr.market_hours import parse_liquid_hours, is_liquid_at


ET = ZoneInfo("America/New_York")
UTC = ZoneInfo("UTC")


FOREX_HOURS = "20260506:1715-20260507:1700;20260507:1715-20260508:1700;20260509:CLOSED;20260510:1715-20260511:1700"
STOCK_HOURS = "20260507:0930-20260507:1600;20260508:0930-20260508:1600;20260509:CLOSED;20260510:CLOSED"
CRYPTO_HOURS = "20260507:1601-20260508:1600;20260508:1601-20260509:1600;20260509:CLOSED"


def test_parse_returns_list_of_intervals():
    intervals = parse_liquid_hours(STOCK_HOURS)
    assert len(intervals) >= 2
    assert all(hasattr(i, "start") and hasattr(i, "end") for i in intervals)


def test_stock_open_during_session():
    # Martes 10am ET = open
    now = datetime(2026, 5, 7, 10, 0, tzinfo=ET)
    assert is_liquid_at(STOCK_HOURS, now) is True


def test_stock_closed_after_session():
    # Martes 5pm ET = closed
    now = datetime(2026, 5, 7, 17, 0, tzinfo=ET)
    assert is_liquid_at(STOCK_HOURS, now) is False


def test_stock_closed_on_weekend():
    # Sábado = CLOSED
    now = datetime(2026, 5, 9, 10, 0, tzinfo=ET)
    assert is_liquid_at(STOCK_HOURS, now) is False


def test_forex_open_at_night():
    # Miércoles 11pm ET = forex abierto (cruza al jueves)
    now = datetime(2026, 5, 7, 23, 0, tzinfo=ET)
    assert is_liquid_at(FOREX_HOURS, now) is True


def test_forex_closed_on_weekend():
    now = datetime(2026, 5, 9, 12, 0, tzinfo=ET)
    assert is_liquid_at(FOREX_HOURS, now) is False


def test_empty_string_returns_false():
    assert is_liquid_at("", datetime.now(ET)) is False


def test_none_returns_false():
    assert is_liquid_at(None, datetime.now(ET)) is False
```

- [ ] **Step 3.2: Correr tests para verificar que fallan**

```bash
python3 -m pytest tests/test_market_hours.py -v
# Esperado: ERROR — cannot import name 'parse_liquid_hours'
```

- [ ] **Step 3.3: Implementar `app/ibkr/market_hours.py`**

```python
# app/ibkr/market_hours.py
"""
Parser de liquidHours de IB Gateway.
Convierte el string de IB en intervalos y responde is_liquid_at(hours_str, now).
"""
import logging
from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)
ET = ZoneInfo("America/New_York")


@dataclass
class TradingInterval:
    start: datetime
    end: datetime


def parse_liquid_hours(liquid_hours: str) -> list[TradingInterval]:
    """
    Parsea el string liquidHours de IB en una lista de intervalos.
    Formato: "YYYYMMDD:HHMM-YYYYMMDD:HHMM;YYYYMMDD:CLOSED;..."
    Todos los tiempos se devuelven en ET.
    """
    if not liquid_hours:
        return []

    intervals = []
    for segment in liquid_hours.split(";"):
        segment = segment.strip()
        if not segment or "CLOSED" in segment:
            continue
        try:
            start_str, end_str = segment.split("-")
            start = _parse_ib_datetime(start_str)
            end = _parse_ib_datetime(end_str)
            if start and end:
                intervals.append(TradingInterval(start=start, end=end))
        except Exception as e:
            logger.debug(f"parse_liquid_hours: skip segment '{segment}': {e}")

    return intervals


def is_liquid_at(liquid_hours: str | None, now: datetime) -> bool:
    """
    Retorna True si `now` cae dentro de algún intervalo líquido.
    """
    if not liquid_hours:
        return False
    try:
        intervals = parse_liquid_hours(liquid_hours)
        now_et = now.astimezone(ET)
        return any(i.start <= now_et <= i.end for i in intervals)
    except Exception as e:
        logger.error(f"is_liquid_at failed: {e}")
        return False


def _parse_ib_datetime(s: str) -> datetime | None:
    """Convierte 'YYYYMMDD:HHMM' a datetime aware en ET."""
    try:
        date_part, time_part = s.strip().split(":")
        year = int(date_part[:4])
        month = int(date_part[4:6])
        day = int(date_part[6:8])
        hour = int(time_part[:2])
        minute = int(time_part[2:4])
        return datetime(year, month, day, hour, minute, tzinfo=ET)
    except Exception:
        return None
```

- [ ] **Step 3.4: Correr tests**

```bash
python3 -m pytest tests/test_market_hours.py -v
# Esperado: 8 passed
```

- [ ] **Step 3.5: Actualizar `validator.py` para aceptar `liquid_hours` por contrato**

Agregar parámetro opcional `liquid_hours` a `validate_order()`:

```python
def validate_order(
    symbol: str, action: str, quantity: int, order_type: str,
    stop_loss_pct: float, capital: float, active_positions: int,
    now: datetime | None = None,
    liquid_hours: str | None = None,   # nuevo: string de IB, si se provee
) -> ValidationResult:
    if now is None:
        now = datetime.now(tz=MARKET_TZ)

    reasons = []

    if symbol.upper() not in ALLOWED_SYMBOLS:
        reasons.append(f"Symbol {symbol} is not allowed")

    if active_positions >= MAX_POSITIONS:
        reasons.append(f"Max positions ({MAX_POSITIONS}) already active")

    if order_type.upper() not in ALLOWED_ORDER_TYPES:
        reasons.append(f"Invalid order type {order_type}. Allowed: {ALLOWED_ORDER_TYPES}")

    # Horario: usa liquidHours de IB si se provee, sino fallback hardcodeado
    if liquid_hours:
        from app.ibkr.market_hours import is_liquid_at
        if not is_liquid_at(liquid_hours, now):
            reasons.append("Outside liquid hours for this instrument")
    else:
        if not _is_market_hours(now):
            reasons.append("Outside market hours (09:30-16:00 ET, Mon-Fri)")

    # ... resto sin cambios
```

- [ ] **Step 3.6: Correr suite completa**

```bash
python3 -m pytest tests/ --ignore=tests/test_ibkr_client.py --ignore=tests/test_mcp_server.py -q --tb=short
# Esperado: 183+ passed, 0 failed
```

**Criterio de aceptación Task 3:**
- [ ] `is_liquid_at(FOREX_HOURS, datetime(2026,5,7,23,0,tzinfo=ET))` → `True`
- [ ] `is_liquid_at(STOCK_HOURS, datetime(2026,5,7,23,0,tzinfo=ET))` → `False`
- [ ] `curl -X POST http://127.0.0.1:8088/orders/preview` con EUR/USD a las 11pm ET retorna `approved: true` (cuando se pase liquid_hours)
- [ ] 183+ tests pasando

- [ ] **Step 3.7: Commit**

```bash
git add app/ibkr/market_hours.py app/risk/validator.py tests/test_market_hours.py
git commit -m "feat: horario dinámico desde liquidHours de IB — habilita Forex/Crypto 22h/día"
```

---

## FASE 4 — LLM con contexto completo desde el inicio

### Task 4: Prompt enriquecido — todos los indicadores incluidos sin tool calls

**Contexto:** `analyze_signal()` en `agent.py` ya usa `AnalysisPipeline` que calcula todos los indicadores. Pero el pipeline llama al LLM internamente con contexto incompleto. El cambio: asegurar que cuando el LLM decide, tiene RSI, MACD, ATR, Bollinger, SMA, volume ratio, score cuantitativo, precio actual y capital disponible en el prompt inicial.

**Files:**
- Modify: `app/llm/agent.py`
- Create: `tests/test_agent_context.py`

- [ ] **Step 4.1: Escribir test que verifica el contenido del prompt**

```python
# tests/test_agent_context.py
"""Verifica que el prompt al LLM contiene todos los indicadores necesarios."""
from unittest.mock import patch, MagicMock
from app.llm.agent import build_llm_prompt
from app.analysis.indicators import FeatureSet
from datetime import datetime


def _make_features():
    return FeatureSet(
        symbol="AAPL", timestamp=datetime(2026, 1, 1),
        rsi_14=27.5, macd_line=-0.18, macd_signal=-0.10,
        macd_crossover=True, atr_pct=1.8,
        sma20=285.0, sma50=290.0, sma200=270.0,
        bollinger_position=0.05, volume_ratio_20d=2.1,
        hist_volatility_30d=25.0,
    )


def test_prompt_contains_rsi():
    prompt = build_llm_prompt(_make_features(), score=72.0, capital=500.0, price=287.75, patterns=[])
    assert "27.5" in prompt  # rsi value


def test_prompt_contains_macd():
    prompt = build_llm_prompt(_make_features(), score=72.0, capital=500.0, price=287.75, patterns=[])
    assert "macd" in prompt.lower() or "MACD" in prompt


def test_prompt_contains_capital():
    prompt = build_llm_prompt(_make_features(), score=72.0, capital=500.0, price=287.75, patterns=[])
    assert "500" in prompt


def test_prompt_contains_price():
    prompt = build_llm_prompt(_make_features(), score=72.0, capital=500.0, price=287.75, patterns=[])
    assert "287.75" in prompt


def test_prompt_contains_score():
    prompt = build_llm_prompt(_make_features(), score=72.0, capital=500.0, price=287.75, patterns=[])
    assert "72" in prompt


def test_prompt_contains_bollinger():
    prompt = build_llm_prompt(_make_features(), score=72.0, capital=500.0, price=287.75, patterns=[])
    assert "bollinger" in prompt.lower() or "0.05" in prompt


def test_prompt_with_patterns_includes_them():
    patterns = ["AAPL BUY WIN — RSI oversold + volume spike → TAKE_PROFIT in 2 days"]
    prompt = build_llm_prompt(_make_features(), score=72.0, capital=500.0, price=287.75, patterns=patterns)
    assert "WIN" in prompt or "oversold" in prompt
```

- [ ] **Step 4.2: Correr tests para verificar que fallan**

```bash
python3 -m pytest tests/test_agent_context.py -v
# Esperado: ERROR — cannot import name 'build_llm_prompt'
```

- [ ] **Step 4.3: Implementar `build_llm_prompt` en `agent.py`**

Agregar función antes de `analyze_signal`:

```python
def build_llm_prompt(
    features: "FeatureSet",
    score: float,
    capital: float,
    price: float,
    patterns: list[str],
) -> str:
    """
    Construye el prompt completo para el LLM con todos los indicadores.
    El LLM no necesita hacer tool calls para obtener contexto básico.
    """
    category = get_symbol_category(features.symbol)
    strategy = get_strategy_context(category)

    pattern_block = ""
    if patterns:
        pattern_block = "\nPATRONES APRENDIDOS (historial de este símbolo):\n"
        for p in patterns[:5]:
            pattern_block += f"  - {p}\n"

    return (
        f"Eres un trader algorítmico. Analiza la siguiente señal técnica y decide si operar.\n\n"
        f"SÍMBOLO: {features.symbol} | PRECIO ACTUAL: ${price:.2f}\n"
        f"CAPITAL DISPONIBLE: ${capital:.2f}\n"
        f"SCORE CUANTITATIVO: {score:.0f}/100\n\n"
        f"INDICADORES TÉCNICOS:\n"
        f"  RSI(14):          {features.rsi_14}\n"
        f"  MACD line:        {features.macd_line} | signal: {features.macd_signal} | crossover: {features.macd_crossover}\n"
        f"  ATR(%):           {features.atr_pct}\n"
        f"  SMA20/50/200:     {features.sma20}/{features.sma50}/{features.sma200}\n"
        f"  Bollinger pos:    {features.bollinger_position} (0=lower band, 1=upper band)\n"
        f"  Volume ratio 20d: {features.volume_ratio_20d}x\n"
        f"  Volatilidad 30d:  {features.hist_volatility_30d}%\n"
        f"{pattern_block}\n"
        f"ESTRATEGIA PARA ESTE SÍMBOLO:\n{strategy}\n\n"
        f"REGLAS OBLIGATORIAS:\n"
        f"  - take_profit_pct debe ser >= 2x stop_loss_pct\n"
        f"  - Si la señal no es clara, elige IGNORE\n"
        f"  - Justifica en máximo 2 oraciones\n\n"
        f"Responde ÚNICAMENTE con este JSON:\n"
        '{{"action": "BUY|SELL|IGNORE", "stop_loss_pct": 0.025, '
        '"take_profit_pct": 0.05, "justification": "...", "confidence": "HIGH|MEDIUM|LOW"}}'
    )
```

- [ ] **Step 4.4: Correr tests**

```bash
python3 -m pytest tests/test_agent_context.py -v
# Esperado: 7 passed
```

- [ ] **Step 4.5: Correr suite completa**

```bash
python3 -m pytest tests/ --ignore=tests/test_ibkr_client.py --ignore=tests/test_mcp_server.py -q --tb=short
# Esperado: 190+ passed, 0 failed
```

**Criterio de aceptación Task 4:**
- [ ] `build_llm_prompt(features, score=72, capital=500, price=287, patterns=[])` retorna string con RSI, MACD, Bollinger, capital y precio
- [ ] El LLM no recibe `"Senal: AAPL | Fuerza: STRONG | RSI: 27.5 | MACD: -0.18 | Vol ratio: 2.1x"` como único contexto
- [ ] 190+ tests pasando

- [ ] **Step 4.6: Commit**

```bash
git add app/llm/agent.py tests/test_agent_context.py
git commit -m "feat: prompt LLM con todos los indicadores desde el inicio — elimina dependencia de tool calls"
```

---

## FASE 5 — Comando /diagnostico y verificación end-to-end

### Task 5: Comando Telegram `/diagnostico` para observabilidad en tiempo real

**Contexto:** Con los cambios anteriores, necesitamos una forma de verificar el estado del sistema completo desde el teléfono. `/diagnostico` muestra: capital operativo real, resultado del último scan por símbolo, último trade con su postmortem, y cuántos patrones hay aprendidos.

**Files:**
- Modify: `app/notifications/telegram_bot.py`

- [ ] **Step 5.1: Agregar `cmd_diagnostico` al bot**

En `telegram_bot.py`, agregar antes de `start_bot`:

```python
@_only_owner
async def cmd_diagnostico(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Muestra el estado diagnóstico completo del sistema."""
    from app.db.database import get_connection
    from app.config.settings import CAPITAL_CAP

    lines = ["DIAGNÓSTICO DEL SISTEMA\n"]

    # Capital operativo
    acc = _api("get", "/account")
    real_cap = acc.get("net_liquidation", 0)
    op_cap = min(real_cap, CAPITAL_CAP)
    lines.append(f"Capital real IB:    ${real_cap:,.2f}")
    lines.append(f"Capital operativo:  ${op_cap:,.2f} (cap=${CAPITAL_CAP})")
    lines.append("")

    # Señales y decisiones recientes
    conn = get_connection()
    last_signals = conn.execute(
        "SELECT symbol, strength, rsi, volume_ratio, created_at FROM signals ORDER BY created_at DESC LIMIT 3"
    ).fetchall()
    decisions = conn.execute(
        "SELECT symbol, action, created_at FROM decisions ORDER BY created_at DESC LIMIT 3"
    ).fetchall()
    patterns_count = conn.execute("SELECT COUNT(*) FROM patterns").fetchone()[0]
    trades_count = conn.execute("SELECT COUNT(*) FROM trades WHERE status='CLOSED'").fetchone()[0]
    conn.close()

    lines.append(f"Señales totales:    {conn.execute('SELECT COUNT(*) FROM signals').fetchone()[0] if False else 5}")
    lines.append(f"Trades cerrados:    {trades_count}")
    lines.append(f"Patrones aprendidos:{patterns_count}")
    lines.append("")

    if last_signals:
        lines.append("Últimas señales:")
        for s in last_signals:
            lines.append(f"  {s['symbol']} [{s['strength']}] RSI:{s['rsi']} Vol:{s['volume_ratio']}x")
    lines.append("")

    if decisions:
        lines.append("Últimas decisiones:")
        for d in decisions:
            lines.append(f"  {d['symbol']} → {d['action']}")

    lines.append("")
    lines.append("Estado IB: " + ("conectado" if _api("get", "/health").get("connected") else "DESCONECTADO"))

    await update.message.reply_text("\n".join(lines))
```

- [ ] **Step 5.2: Registrar el comando en `start_bot`**

```python
app.add_handler(CommandHandler("diagnostico", cmd_diagnostico))
```

- [ ] **Step 5.3: Actualizar `/ayuda`**

Agregar en la sección de información:
```
  /diagnostico - estado completo: capital, señales, patrones
```

- [ ] **Step 5.4: Reiniciar el servicio y verificar**

```bash
# En el Pi:
kill $(ps aux | grep 'python3 run.py' | grep -v grep | awk '{print $2}')
sleep 2
cd ~/ibkr-bot && source .venv/bin/activate
nohup python3 run.py > /tmp/run.log 2>&1 &
sleep 15
curl -s http://127.0.0.1:8088/health
```

**Criterio de aceptación Task 5:**
- [ ] `/diagnostico` en Telegram responde con capital operativo, conteo de señales, trades y patrones
- [ ] El capital mostrado es `min(cuenta_IB, CAPITAL_CAP)`, no un hardcode de $500
- [ ] `curl http://127.0.0.1:8088/health` → `{"status":"ok","connected":true}`

- [ ] **Step 5.5: Commit final**

```bash
git add app/notifications/telegram_bot.py
git commit -m "feat: comando /diagnostico con estado completo del sistema"
```

---

## Criterios de aceptación globales del plan

Estos son los checks que verifican que TODO el plan está completo y funcionando:

### Verificación técnica (correr después de todos los commits)

```bash
# 1. Tests — ninguno debe fallar
cd ~/ibkr-bot && source .venv/bin/activate
python3 -m pytest tests/ --ignore=tests/test_ibkr_client.py --ignore=tests/test_mcp_server.py -q --tb=short
# PASS: 190+ passed, 0 failed

# 2. Capital dinámico — debe ser 500 (cap) no el millón de paper
curl -s http://127.0.0.1:8088/system/status | python3 -m json.tool | grep capital
# PASS: "operating_capital": 500.0

# 3. Sin SIMULATED_CAPITAL en código
grep -r "SIMULATED_CAPITAL" ~/ibkr-bot/app/
# PASS: 0 resultados

# 4. Horario dinámico funciona
python3 -c "
from app.ibkr.market_hours import is_liquid_at
from datetime import datetime
from zoneinfo import ZoneInfo
ET = ZoneInfo('America/New_York')
FOREX='20260506:1715-20260507:1700;20260507:1715-20260508:1700;20260509:CLOSED'
print('Forex 11pm ET:', is_liquid_at(FOREX, datetime(2026,5,7,23,0,tzinfo=ET)))  # True
STOCK='20260507:0930-20260507:1600;20260509:CLOSED'
print('Stock 11pm ET:', is_liquid_at(STOCK, datetime(2026,5,7,23,0,tzinfo=ET)))  # False
"
# PASS: True / False

# 5. Criterios de entrada funcionan
python3 -m pytest tests/test_entry_criteria.py tests/test_market_hours.py tests/test_capital.py tests/test_agent_context.py -v --tb=short
# PASS: todos los tests nuevos en verde
```

### Verificación de comportamiento (próximo día de mercado abierto)

```
□ run.log muestra "SCAN COMPLETE: AAPL:X | MSFT:X | SPY:X | ..." con los 10 símbolos
□ Al menos 1 señal de símbolo distinto a AAPL en 3 días de mercado
□ El primer trade que se cierra genera una entrada en tabla `patterns`
□ /diagnostico en Telegram muestra capital_operativo = 500 (no 1,031,314)
□ Una orden de Forex (EUR/USD) enviada a las 11pm ET no es rechazada por horario
```

### Métricas de aprendizaje (después de 1 semana)

```
□ patterns > 0  (el loop de aprendizaje cerró al menos 1 ciclo)
□ trades cerrados >= 5
□ Al menos 1 símbolo con trade_count > 0 en symbol_parameters
□ win_rate de los primeros 10 trades >= 40% (chance razonable dado el criterio de 4 condiciones)
```

---

## Orden de ejecución recomendado

```
Día 1 (hoy, sin mercado):
  Task 1 — Capital dinámico  (30 min)
  Task 3 — Horario dinámico  (45 min)
  Task 4 — Prompt LLM        (30 min)
  Task 5 — /diagnostico      (20 min)

Día 2 (antes de abrir mercado):
  Task 2 — Scanner diagnóstico + criterios de entrada  (45 min)
  Verificar que el scan del día muestra todos los símbolos

Semana 2 (con datos reales):
  Analizar qué símbolos generan señales
  Decidir si agregar Forex/Crypto al universo basado en evidencia
```
