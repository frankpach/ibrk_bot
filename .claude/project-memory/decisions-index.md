# Decisions Index

## refactor / hexagonal-arch (2026-05-15)

Full decisions: `docs/04-modules/refactor/DECISIONS.md`

| ID | Decision | Why |
|----|----------|-----|
| DEC-001 | SQLAlchemy ORM (not raw SQL) | Portable SQLite→PostgreSQL; 1277-line monolith eliminated |
| DEC-002 | Alembic migrations | Versioned, reversible; `alembic upgrade head` at startup |
| DEC-003 | Ports & Adapters (Hexagonal) | Use cases testable without IB Gateway or Telegram |
| DEC-004 | Eliminate internal HTTP (httpx self-calls) | Circular dependency; coupled to FastAPI server being up |
| DEC-005 | EventBus in-process synchronous | No Redis; predictable order; no `unsubscribe()` — register handlers once at container init ONLY |
| DEC-006 | Persist state in `control_settings` DB | Restart preserves mode/pause |
| DEC-007 | Control plane at `/control` (React SPA) | Browser config without SSH |
| DEC-008 | Two-tier auth: Control-Key + Admin-Key | Prevent accidental live mode activation |
| DEC-009 | ThreadPoolExecutor max_workers=3 for slow jobs | LLM analysis (150s+) must not block HTTP |
| DEC-010 | Fernet encryption for secrets | API keys never in plain text |
| DEC-011 | Dual-backend SQLite/PostgreSQL | Future migration path without code changes |
| DEC-012 | Container as single wiring point | `get_container()` (singleton) + `test_container()` (fresh, mocked) |
| DEC-013 | `compat.py` as migration bridge | 75 legacy functions — not to be extended; being replaced by Repositories |
| DEC-014 | `get_deduplicator()` as thin Container delegate | Backward compat while call sites migrate to `container.order_deduplicator` |

## live-dashboard (2026-05-13)

Full decisions: `docs/dev/artifacts/live-dashboard/05-why-decisions.md`

| ID | Decision | Why |
|----|----------|-----|
| WD-01 | Jobs write to DB, dashboard reads — zero IBKR calls from /dashboard/data endpoint | IBKR single-session constraint; mobile app disconnects gateway |
| WD-02 | position_snapshots written inside check_positions(), not a separate job | Reuses existing price fetch at zero extra IBKR rate limit cost |
| WD-03 | SVG inline charts, no charting library (Chart.js etc.) | Pi 5 ARM + slow Tailscale mobile: external chart libs (~200KB each) unacceptable |
| WD-04 | news_cache fetches full universe (40 symbols) every 10min, not on-demand | Gateway may be offline when user clicks tab; cache ensures always-on data |
| WD-05 | run_learning_cycle() receives ib_client as optional param (not global import) | Avoids circular imports; keeps module testable with mocks |
| WD-06 | backtest_profit_factor added to symbol_parameters, not new table | One calibration result per symbol; no historical query use case |
| WD-07 | Telegram confirmation for close position, not web PIN | Leverages existing @_only_owner security; natural audit trail in chat |
