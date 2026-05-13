# Constraints: live-dashboard

**Module**: live-dashboard
**Date**: 2026-05-13

## Global Rules

- No breaking changes to trading pipeline (check_positions, scanner, llm/loop)
- Fallback graceful on every new component — if it fails, bot keeps running
- SQLite only — no new DB engines
- All DB migrations via `_add_column_if_missing()` — idempotent

## Module-Specific Constraints

### IB Gateway single-session constraint
Opening IBKR mobile/web app disconnects IB Gateway. The dashboard MUST NOT require IB Gateway to be online to render. All data is served from SQLite cache. Each dashboard section shows "last updated X min ago" from the fetch timestamp in the cache tables.

### Zero IBKR calls from /dashboard/data
The endpoint only does SELECT queries. All IBKR interaction happens in APScheduler jobs that run regardless of whether anyone is viewing the dashboard.

### Rate limit awareness for new jobs
Current jobs already use ~15-20 requests/min peak. New jobs (_fetch_news, _fetch_scanner, _fetch_sectors) must:
- Only run during market hours for STK/FUT (use `is_liquid_at()` check)
- Include `time.sleep(0.5)` between symbol iterations in news fetch
- News fetch: max 40 symbols × 1 request = 40 req/10min (within 50 req/10min limit)

### Pi ARM performance
- No npm/webpack/build step — React via CDN only
- Charts as inline SVG — no Chart.js, Recharts, or D3 (too heavy for ARM)
- `/dashboard/data` response must be < 50KB
- No server-side rendering of charts

### Authentication
Phase 1 (this module): no auth. Dashboard is read-only with Telegram confirmation for actions. Only accessible via Tailscale network (trusted).

Phase 2 (future): PIN or bearer token before enabling direct write actions without Telegram confirmation.

### Dashboard rebuild strategy
`app/api/dashboard.py` is a full rewrite. The existing `render_dashboard_html()` function signature is kept (returns str) — only the content changes. The legacy `render_dashboard()` shim is also kept for backwards compatibility with any tests.

## Module Dependencies

| Module | Direction | Description |
|--------|-----------|-------------|
| `app/positions/manager.py` | Modified | Add position_snapshot write in check_positions() |
| `app/ml/cycle.py` | Modified | Add ib_client param + account_snapshot write |
| `app/db/database.py` | Modified | 4 new tables + new CRUD functions |
| `app/db/models.py` | Modified | Add 3 fields to SymbolParameter |
| `app/api/main.py` | Modified | Enrich /dashboard/data endpoint |
| `app/api/dashboard.py` | Rewritten | All new sections |
| `run.py` | Modified | 5 new scheduler jobs |
| `app/scanner/news_fetcher.py` | New | News batch fetch + persist |
| `app/scanner/market_scanner.py` | New | Scanner + sector + implied_move fetch |
| `app/analysis/data.py` | Possibly extended | get_news() may need multi-symbol variant |
