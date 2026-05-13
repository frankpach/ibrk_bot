# Architecture Map: risk-engine-v2

## Existing Components

The risk engine currently consists of:
- `app/risk/validator.py`: `validate_order()` — checks symbol approval, position count, order type, market hours, capital.
- `app/positions/manager.py`: `check_positions()` — checks SL/TP static levels, closes positions.
- `app/config/settings.py`: Static constants — `MAX_RISK_PCT=0.02`, `MAX_POSITION_USD=500`, `CIRCUIT_BREAKER_PCT=0.05`.
- `app/api/main.py`: `orders_preview()` and `orders_place()` — calculate position size using `max_risk_usd / stop_loss_pct`.
- `app/analysis/scorer.py`: `compute_score()` — returns 0-100 score with dimensions.

## Existing Events / Patterns

- `check_positions()` runs every 2 minutes via APScheduler.
- `validate_order()` is called before every order placement.
- No market regime detection exists.
- No time-of-day filtering exists.

## Existing Models

- `Trade` model: entry_price, stop_loss_price, take_profit_price (static after entry).
- `SymbolParameter` model: per-symbol multipliers for scoring (not used for risk).
- No `MarketRegime` or `PositionState` tracking.

## Gaps Identified

1. **No trailing stop**: SL is fixed forever after entry.
2. **No breakeven stop**: Never protects entry price after initial move.
3. **No dynamic sizing**: Size = `max_risk / sl_pct` always, ignoring win rate and volatility.
4. **No slippage buffer**: Assumes perfect fills.
5. **No market regime filter**: VIX, sector rotation, macro ignored.
6. **No time-of-day filter**: Enters at 9:31 AM with same rules as 11:00 AM.
7. **Only MKT orders**: No LMT for entries.

## New Components Needed

1. `app/risk/dynamic_sizing.py`: `calculate_position_size()` with win rate, ATR, score confidence, slippage buffer.
2. `app/risk/trailing_stop.py`: `update_stop_levels()` — breakeven rule, trailing rule.
3. `app/risk/market_regime.py`: `get_regime()` — VIX-based regime detector with adjustments.
4. `app/risk/time_filter.py`: `is_entry_allowed()` — time-of-day and day-of-week filter.
5. `app/risk/slippage.py`: `estimate_slippage()` — spread-based position size reduction.

## Components to Reuse

- `IBDataLayer.get_ohlcv("VIX", ...)` for regime detection.
- `SymbolParameter` table for per-symbol win rates and adjusted SL.
- `Trade` model — extend with `current_stop_price` dynamic field (or calculate on the fly).
- `validate_order()` — extend with regime and time checks.

## Anti-Patterns Detected

- **Anti-Pattern: Static SL/TP forever**: Trade model stores SL/TP at entry time and never updates.
- **Anti-Pattern: Linear sizing formula**: Ignores that high volatility requires smaller size, and high confidence allows larger size.
- **Anti-Pattern: MKT-only orders**: Causes unnecessary slippage on entries.

## Module Dependencies

| Module | Relationship |
|--------|-------------|
| `dev-plan` (risk/validator) | Will be extended with regime and time filters |
| `dev-plan` (positions/manager) | Will call trailing_stop updater |
| `dev-plan` (api/main) | Will use dynamic sizing for preview |
| `dev-plan` (analysis/scorer) | Win rate and score feed into sizing |
| `dev-plan` (analysis/data) | VIX data for regime detection |
