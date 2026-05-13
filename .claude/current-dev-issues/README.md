# mtf-learning-engine — Development Issues

**Module**: mtf-learning-engine
**Started**: 2026-05-13
**Status**: Phase 5 — Execution ready
**PRD**: docs/dev/artifacts/mtf-learning-engine/08-prd.md

---

## Active Issues — Iteración 1 (deadline: 2026-05-20)

| Issue | Título | Effort | Bloqueado por | Estado |
|-------|--------|--------|---------------|--------|
| MTE-001 | Fix _dim_volatility() — invertir escala ATR | S | — | pending |
| MTE-002 | Fix _dim_price_change() — dirección sin abs() | S | — | pending |
| MTE-003 | LMT Limit Price en _execute_order() | XS | — | pending |
| MTE-004 | Telegram /notificaciones + /silencio + Digest Scheduler | S | — | pending |
| MTE-005 | Fix SignalFilter.retrain() + Migración DB | M | — | pending |
| MTE-006 | Activar df_hourly en compute_features() | S | MTE-005 | pending |
| MTE-007 | Weekly Trend Filter + Fix Multi-Market Preprocessor | M | MTE-006 | pending |
| MTE-008 | Learning Cycle Coordinator — app/ml/cycle.py | M | MTE-005, MTE-006 | pending |

## Active Issues — Iteración 2

| Issue | Título | Effort | Bloqueado por | Estado |
|-------|--------|--------|---------------|--------|
| MTE-011 | DB Helpers: get_closed_trades_by_symbol() | XS | MTE-005 | pending |
| MTE-009 | Postmortem con Contexto Estadístico | S | MTE-008, MTE-011 | pending |
| MTE-010 | Backtest Calibration — on_symbol_approved() | M | MTE-008 | pending |

## Dependency Graph

```
Sin dependencias (Grupo A — paralelos entre sí):
  MTE-001  Fix volatility scorer
  MTE-002  Fix price_change scorer
  MTE-003  LMT limit price
  MTE-004  Telegram commands + digest
  MTE-005  Retrain fix + DB migration  ◄── CRÍTICO

Grupo B — después de MTE-005:
  MTE-006  Activar hourly features
  MTE-011  DB helpers

Grupo C — después de MTE-005 + MTE-006:
  MTE-007  Weekly trend filter + multi-market
  MTE-008  Learning cycle coordinator

Grupo D — después de MTE-008:
  MTE-009  Postmortem stats (+ MTE-011)
  MTE-010  Backtest calibration
```

## Orden de ejecución recomendado

```
1. MTE-001  mínimo riesgo, solo scorer.py
2. MTE-002  mínimo riesgo, solo scorer.py
3. MTE-003  XS, solo loop.py
4. MTE-004  S, telegram + run.py scheduler
5. MTE-005  M, DB migration + retrain fix (CRÍTICO)
6. MTE-006  S, activar hourly en indicators.py
7. MTE-007  M, weekly + multi-market preprocessor
8. MTE-008  M, app/ml/cycle.py (nuevo)
--- Iteración 2 ---
9. MTE-011  XS, DB helpers
10. MTE-009  S, app/ml/postmortem_stats.py (nuevo)
11. MTE-010  M, app/ml/calibration.py (nuevo)
```

---

## Issues de módulos anteriores (done/)

| Issue | Módulo | Estado |
|-------|--------|--------|

---

## Issue List

### notification-system

| # | Title | Priority | Effort | Blocked by | Status |
|---|---|---|---|---|---|
| NS-001 | NotificationThrottler + NotificationQueue | P0 | M | — | ✅ done |
| NS-002 | ApprovalManager (Async Callbacks) | P0 | M | NS-001 | ✅ done |
| NS-003 | NotificationPolicy + Digest + Commands | P1 | S | NS-001 | ✅ done |
| NS-004 | OrderExecutionMonitor + Fill Verification | P0 | M | NS-001 | ✅ done |
| NS-005 | Order Deduplication + Pre-flight Checks | P1 | S | NS-004 | ✅ done |

### risk-engine-v2

| # | Title | Priority | Effort | Blocked by | Status |
|---|---|---|---|---|---|
| RE-001 | PositionSizer + SlippageEstimator | P0 | M | — | ✅ done |
| RE-002 | TrailingStopManager | P0 | M | RE-001 | ✅ done |
| RE-003 | MarketRegimeDetector + TimeFilter | P1 | S | — | ✅ done |
| RE-004 | LMT Orders + Integration | P1 | S | RE-001, RE-003 | ✅ done |
| RE-005 | Order Lifecycle State Machine (DB) | P0 | M | — | ✅ done |
| RE-006 | Real Fill Price Tracking | P1 | S | RE-005 | ✅ done |
| RE-007 | ATR-Based Adaptive Stop Loss | P0 | S | — | ✅ done |
| RE-008 | Partial Exits (Escalonado de Ganancias) | P1 | M | RE-002, RE-007 | ✅ done |
| RE-009 | Re-entry Rules + Cooldown | P0 | S | — | ✅ done |
| RE-010 | ML Ligero como Filtro Previo | P1 | L | RE-001 | ✅ done |
| RE-011 | Drawdown Recovery Strategy | P0 | M | RE-001 | ✅ done |

---

## Done

- [x] **RE-005** — Order Lifecycle State Machine (DB schema + migration + tests)
- [x] **NS-001** — NotificationThrottler + NotificationQueue (core + tests)
- [x] **RE-007** — ATR-Based Adaptive Stop Loss (core + tests)
- [x] **RE-009** — Re-entry Rules + Cooldown (core + tests)
- [x] **RE-001** — PositionSizer + SlippageEstimator (core + tests)
- [x] **RE-003** — MarketRegimeDetector + TimeFilter (core + tests)
- [x] **RE-011** — Drawdown Recovery Strategy (core + tests)
- [x] **NS-002** — ApprovalManager Async Callbacks (core + tests)
- [x] **NS-003** — NotificationPolicy + DigestGenerator (core + tests)
- [x] **NS-004** — OrderExecutionMonitor + fill verification (core + tests)
- [x] **NS-005** — OrderDeduplicator + PreflightChecker (core + tests)
- [x] **RE-002** — TrailingStopManager with breakeven + trailing rules (core + tests)
- [x] **RE-004** — LMT order calculator + API auto-conversion (core + tests)
- [x] **RE-006** — FillTracker + fallback from executions (core + tests)
- [x] **RE-008** — PartialExitManager 50% gain-taking (core + tests)
- [x] **RE-010** — SignalFilter lightweight ML pre-filter (core + tests)

---

## Test Suite

- **681 tests passed, 0 failed**
- **Coverage: 80%** (3,949 / 4,916 statements)

## Next Steps

All planned issues for notification-system + risk-engine-v2 are complete. Potential follow-ups (out of scope for this batch):

1. Increase coverage from 80% → 90% by testing remaining branches in `telegram_bot.py`, `ml/signal_filter.py`, and `ibkr/client.py`.
2. Integration test: end-to-end paper trade with LMT entry → partial exit → trailing stop → close.
3. Model training pipeline for `SignalFilter.retrain()` with real closed trade data.
4. Telegram bot command expansion (`/modo`, `/escaner`, `/rendimiento`).
