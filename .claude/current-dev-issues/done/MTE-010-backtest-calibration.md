# Issue MTE-010: Backtest Calibration — on_symbol_approved()

**Module**: mtf-learning-engine
**Type**: AFK
**Effort**: M
**Blocked by**: MTE-008
**Requires review**: false
**Iteración**: 2

---

## WHY — The Human Problem

**User pain**: Todo símbolo nuevo arranca con SL=2.5%, TP=6% genéricos sin importar su comportamiento histórico. ES (futuro S&P500) y BTC (crypto) tienen volatilidades completamente distintas — usar los mismos defaults para ambos garantiza parámetros subóptimos.

**Business impact**: Los primeros 5-10 trades de cada símbolo nuevo son el período más arriesgado porque los parámetros no están calibrados. Con backtest histórico, ese período se elimina.

**Success signal**: Al aprobar ES, el sistema corre un grid search en 180 días de historia, encuentra que SL=3.0% y TP=7% tiene el mejor profit_factor, escribe eso a `symbol_parameters`, y Frank recibe una notificación en Telegram.

---

## WHO

| Persona | Role | Device | Environment | Goal | Constraint |
|---------|------|--------|-------------|------|------------|
| Frank Developer | Quant | Desktop | Home office | Símbolo nuevo arranca calibrado | No bloquear la aprobación |
| Motor Autónomo | Sistema | Raspberry Pi | Background thread | Grid search sin interrumpir scanner | Rate limit IBKR |

---

## WHAT — Constraints

- [ ] Thread daemon — nunca bloquear `approve_symbol()`
- [ ] Delay de 2s entre requests IBKR en el grid search
- [ ] Si ninguna combinación tiene >= 5 trades → usar defaults y loggear (no crashear)
- [ ] Grid: SL en [0.02, 0.025, 0.03, 0.035], TP en [0.04, 0.05, 0.06, 0.07, 0.08] = 20 combinaciones
- [ ] `backtest_calibrated` y `backtest_calibrated_at` deben existir en `symbol_parameters` (MTE-006 ya agrega las columnas)
- [ ] Solo modificar `app/ml/calibration.py` (nuevo) y `app/db/database.py` (hook en approve_symbol)

---

## HOW — Implementation Approach

**`app/ml/calibration.py`** (nuevo, ~80 líneas):

```python
import threading
import time
import logging
from app.db.database import update_symbol_parameters
from app.backtest.engine import run_backtest
from app.notifications.telegram import notify

logger = logging.getLogger(__name__)

SL_GRID = [0.020, 0.025, 0.030, 0.035]
TP_GRID = [0.040, 0.050, 0.060, 0.070, 0.080]
MIN_TRADES_VALID = 5
PERIOD_DAYS = 180
REQUEST_DELAY = 2.0  # segundos entre requests IBKR


def on_symbol_approved(symbol: str, ib_client) -> None:
    """Non-blocking: lanza calibración en background thread."""
    t = threading.Thread(
        target=_run_calibration_safe,
        args=(symbol, ib_client),
        daemon=True,
        name=f"calibration-{symbol}"
    )
    t.start()
    logger.info(f"Calibration started for {symbol} in background")


def _run_calibration_safe(symbol: str, ib_client) -> None:
    try:
        best_result = None
        best_sl = 0.025
        best_tp = 0.060

        for sl in SL_GRID:
            for tp in TP_GRID:
                time.sleep(REQUEST_DELAY)
                try:
                    result = run_backtest(
                        symbol=symbol,
                        ib_client=ib_client,
                        period_days=PERIOD_DAYS,
                        stop_loss_pct=sl,
                        take_profit_pct=tp,
                        capital=500.0,
                    )
                    if result.total_trades >= MIN_TRADES_VALID:
                        if best_result is None or result.profit_factor > best_result.profit_factor:
                            best_result = result
                            best_sl = sl
                            best_tp = tp
                except Exception as e:
                    logger.warning(f"Backtest {symbol} SL={sl} TP={tp} failed: {e}")

        from datetime import datetime
        update_symbol_parameters(
            symbol,
            stop_loss_pct=best_sl,
            take_profit_pct=best_tp,
            backtest_calibrated=1,
            backtest_calibrated_at=datetime.utcnow().isoformat(),
        )

        if best_result:
            notify(
                f"📊 <b>{symbol}</b> calibrado:\n"
                f"SL={best_sl:.1%} TP={best_tp:.1%}\n"
                f"Profit factor: {best_result.profit_factor:.2f} "
                f"({best_result.total_trades} trades, {PERIOD_DAYS}d)"
            )
        else:
            notify(f"⚠️ <b>{symbol}</b>: sin datos suficientes para calibrar (usando defaults)")
            logger.warning(f"No valid backtest results for {symbol} — using defaults")

    except Exception as e:
        logger.error(f"Calibration failed for {symbol}: {e}")
```

**`app/db/database.py`** — en `approve_symbol()`, agregar hook al final:
```python
def approve_symbol(symbol: str, ib_client=None) -> None:
    conn = get_connection()
    conn.execute("UPDATE symbol_config SET approved=1 WHERE symbol=?", (symbol.upper(),))
    conn.commit()
    conn.close()
    # Hook de calibración (solo si ib_client disponible)
    if ib_client is not None:
        from app.ml.calibration import on_symbol_approved
        on_symbol_approved(symbol.upper(), ib_client)
```

---

## Code Search

- [x] `app/backtest/engine.py:174-220` — `run_backtest()` leído, acepta sl/tp como parámetros
- [x] `app/db/database.py` — `approve_symbol()` existe, `update_symbol_parameters()` existe
- [x] Columnas `backtest_calibrated` y `backtest_calibrated_at` — agregadas en MTE-006

**Reuse decision**:
- Reuse as-is: `run_backtest()`, `update_symbol_parameters()`, `notify()`
- Build new: `app/ml/calibration.py`, hook en `approve_symbol()`

---

## Reference Documents

| Document | Path | What to Extract |
|----------|------|----------------|
| PRD | `docs/dev/artifacts/mtf-learning-engine/08-prd.md` | REQ-08, AC-08.1 a AC-08.6 |
| Interface design | `docs/dev/artifacts/mtf-learning-engine/06-interface-design.md` | Flujo 4 |
| Why Decisions | `docs/dev/artifacts/mtf-learning-engine/05-why-decisions.md` | WD-06 |

---

## Acceptance Criteria

- [ ] AC-08.1: `approve_symbol("NVDA")` retorna inmediatamente; calibración corre en background
- [ ] AC-08.2: Grid corre 20 combinaciones con delay de 2s entre requests
- [ ] AC-08.3: Si ninguna combinación tiene >= 5 trades → defaults escritos, notificación enviada
- [ ] AC-08.4: `symbol_parameters.backtest_calibrated = 1` tras calibración exitosa
- [ ] AC-08.5: Notificación Telegram con SL%, TP%, profit_factor y número de trades
- [ ] AC-08.6: El scanner sigue operando durante la calibración (thread daemon no bloquea)

## Definition of Done

- [ ] Todos los ACs verificados
- [ ] Test: `on_symbol_approved()` lanza thread y retorna inmediatamente
- [ ] Test: `_run_calibration_safe()` con mock de `run_backtest()` selecciona el mejor resultado
- [ ] Issue movido a `done/`
