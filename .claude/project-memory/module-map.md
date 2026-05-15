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

### arch-refactor — ✓ Complete (2026-05-15)
- **Artifacts**: `docs/dev/artifacts/refactor/`, `docs/04-modules/refactor/`
- **Issues**: 001–010 all complete + Sprint 1 DI fixes
- **Key outcome**: Full Hexagonal Architecture — DI Container, EventBus, SQLAlchemy ORM (23 models), Alembic migrations, Ports/Adapters (IBrokerPort, INotificationPort, ILLMPort), use cases (PlaceOrder, ClosePosition, ChangeMode, PauseSystem, UpdateControlSetting), control plane `/control`, background job runner, two-tier auth, Fernet secrets, systemd hardening
- **Sprint 1 extras**: `AlertManager` class-based DI; `LLMSignalProcessor` class-based DI; `OrderDeduplicator` into Container; `IBrokerPort.get_prev_close()`; `pipeline._score()` uses broker port (no httpx)
- **CI/CD**: `.github/workflows/ci.yml` — pytest + alembic migrations on every push; deploy to aiutox-pi via `scripts/deploy.sh`
- **Backlog**: `docs/04-modules/refactor/BACKLOG.md` — Sprint 2 (wire ILLMPort, replace notify() imports, analysis events, EventBus.unsubscribe)
