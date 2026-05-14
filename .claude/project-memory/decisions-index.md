# Decisions Index

## arch-refactor (2026-05-14)

Full decisions: `docs/04-modules/arch-refactor/DECISIONS.md`

| ID | Decision | Why |
|----|----------|-----|
| D-01 | SQL plano + repositorios (no ORM) | Legible, debuggeable para trading; repositorios dan indirección suficiente sin ORM overhead |
| D-02 | InProcessJobRunner con asyncio (no Celery/ARQ) | Proceso único hoy; interfaz swappable para workers futuros |
| D-03 | X-Control-Key auth (no JWT/OAuth) para control plane | Tailscale reduce exposición; JWT es complejidad sin ganancia para 1 usuario |
| D-04 | No DDD puro — use cases + ports + adapters | Dominio de trading sin Aggregates complejos; separación suficiente para testabilidad |
| D-05 | No CQRS full — read models separados para dashboard | Dashboard agrega 15+ fuentes; DashboardQueryService desacopla presentación sin event sourcing |
| D-06 | Feature flags temporales USE_DIRECT_CALLS para Fases 1–2 | Ruta crítica de trading; flag permite rollback sin revert de código |

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
