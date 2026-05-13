# notification-system + risk-engine-v2 — Development Issues

**Modules**: notification-system, risk-engine-v2
**Started**: 2026-05-12
**Status**: ✅ All issues complete

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
