# Constraints: risk-engine-v2

**Module**: risk-engine-v2
**Last Updated**: 2026-05-12

## Global Rules

See CLAUDE.backend.md and CLAUDE.frontend.md for complete ruleset.

## Module-Specific Constraints

- Must not modify `IBKRClient` directly — only wrap via `IBDataLayer`.
- `validate_order()` must remain the single point of truth for order validation.
- Trailing stop updates must not generate new DB schema changes (compute on the fly or add column).
- VIX data must use existing `IBDataLayer.get_ohlcv()` — no new IB API calls.
- Time filter must use `MARKET_TZ` from settings — no hardcoded timezones.
- Position size calculations must never exceed `MAX_POSITION_USD` or `capital * MAX_RISK_PCT`.
- All new risk rules must be overrideable by Frank via Telegram commands (`/forzar_entrada SYMBOL` for emergencies).
- Backward compatibility: existing trades without dynamic fields must continue working.

## Module Dependencies

| Module | Enabled | depends_on | produces_for | Relationship |
|--------|---------|------------|--------------|--------------|
| dev-plan | ✅ | — | risk-engine-v2 | Core trading logic to be enhanced |
| risk-engine-v2 | ✅ | dev-plan (data, validator, positions) | dev-plan | Enhanced risk rules and position management |
