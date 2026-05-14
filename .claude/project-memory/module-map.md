# Module Map

## Completed Modules

### live-dashboard — ✓ Complete (2026-05-13)
- **Spec**: `docs/superpowers/specs/2026-05-13-live-dashboard-design.md`
- **Artifacts**: `docs/dev/artifacts/live-dashboard/`
- **Issues**: LD-001 through LD-005 — all complete
- **Key outcome**: Dashboard reads from SQLite (jobs write); live P&L, equity curve, news, scanner, symbol training data; SVG charts; smart refresh (15s with positions, 60s idle); Telegram confirmation for critical actions
- **Tables added**: `position_snapshots`, `account_snapshots`, `news_cache`, `scanner_results`
- **Fields added**: `symbol_parameters.backtest_profit_factor`, `symbol_parameters.backtest_calibrated`, `symbol_parameters.backtest_calibrated_at`

### mtf-learning-engine — ✓ Complete (prior)
- **Artifacts**: `docs/dev/artifacts/mtf-learning-engine/`
- **Issues**: MTE-001 through MTE-011 — all complete

### notification-system — ✓ Complete (prior)
- **Artifacts**: `docs/dev/artifacts/notification-system/`
- **Issues**: NS-001 through NS-005 — all complete

### risk-engine-v2 — ✓ Complete (prior)
- **Artifacts**: `docs/dev/artifacts/risk-engine-v2/`
- **Issues**: RE-001 through RE-011 — all complete

## In Progress

### arch-refactor — 🔄 Starting (2026-05-14)
- **Plan**: `C:\Users\be47\.claude\plans\para-el-promp-glowing-quasar.md`
- **Phases**: 0–9 (Fases 0–8 core, Fase 9 opcional)
- **Key goal**: Desacoplar HTTP interno, extraer ports/adapters, persistir system state, control plane /control, SQLite→PostgreSQL path
