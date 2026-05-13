# Next Actions: notification-system + risk-engine-v2

**Modules**: notification-system, risk-engine-v2
**Last Updated**: 2026-05-12

## Current Focus

**Phase**: 5 — Execution
**Goal**: Implementar 16 issues (5 + 11)

## Next Action (Do This Now)

### notification-system:
1. **NS-001** — NotificationThrottler + NotificationQueue (M, desbloquea NS-002/003/004)

### risk-engine-v2 (grupo paralelo):
1. **RE-005** — Order Lifecycle State Machine (M) — cambia schema DB primero
2. **RE-001** — PositionSizer + SlippageEstimator (M)
3. **RE-007** — ATR-Based Adaptive Stop Loss (S)
4. **RE-009** — Re-entry Rules + Cooldown (S)

## Execution Order

### notification-system:
```
NS-001 (throttler + queue)
    ├── NS-002 (approval manager)
    ├── NS-003 (policy + digest)
    └── NS-004 (order monitor + fill verification)
            └── NS-005 (preflight + dedup)
```

### risk-engine-v2:
```
Grupo 1 (paralelo):
    RE-005 (state machine)
    RE-001 (position sizer)
    RE-007 (ATR SL)
    RE-009 (cooldown)
    RE-003 (regime + time)

Grupo 2 (después de Grupo 1):
    RE-002 (trailing stop) — después RE-001 + RE-007
    RE-006 (fill price) — después RE-005
    RE-010 (ML filter) — después RE-001
    RE-011 (drawdown recovery) — después RE-001
    RE-004 (LMT + integration) — después RE-001 + RE-003

Grupo 3 (después de RE-002):
    RE-008 (partial exits) — después RE-002 + RE-007
```

## Completed Phases

- [x] Phase 0 — Discovery (ambos módulos)
- [x] Phase 1 — Architecture (ambos módulos)
- [x] Phase 2 — Design (ambos módulos)
- [x] Phase 3 — Requirements (ambos módulos)
- [x] Phase 4 — Planning (ambos módulos)
- [ ] Phase 5 — Execution
- [ ] Phase 6 — Deploy
- [ ] Phase 7 — Test
- [ ] Phase 8 — Review
