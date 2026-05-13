# Why Decisions: risk-engine-v2

**Module**: risk-engine-v2
**Last Updated**: 2026-05-12

## Decision 1: Trailing stop computed on-the-fly, not stored in DB

**Context**: Could add `current_stop_price` column to `trades` table.
**Decision**: Compute trailing stop dynamically in `check_positions()` based on entry price, current price, and rules.
**Why**: Avoids DB migration. Simpler logic. The stop level is deterministic given the rules and prices.
**Trade-off**: Cannot query "what was the trailing stop at 2 PM?" from DB. Only latest is known.

## Decision 2: VIX as proxy for market regime, not multi-factor model

**Context**: Could use VIX + yield curve + DXY + sector breadth for regime detection.
**Decision**: VIX only. Three regimes: low (<15), normal (15-25), high (>25), crisis (>35).
**Why**: VIX is the strongest single predictor of equity market volatility. Available via IBKR. Simple to implement and explain.
**Trade-off**: Misses bond-market stress or FX-driven moves. Can extend later.

## Decision 3: Kelly Criterion simplified, not full Kelly

**Context**: Full Kelly would be `f* = (bp - q) / b` where b=odds, p=win rate, q=loss rate.
**Decision**: Use a fractional Kelly (1/4 Kelly) as a multiplier on base size, capped at 1.5x and floored at 0.5x.
**Why**: Full Kelly is too aggressive and volatile for a $500 account. Simplified version captures the intuition (better edge = bigger size) without extreme swings.
**Trade-off**: Not mathematically optimal. But robust.

## Decision 4: Time-of-day filter hardcoded, not configurable per-symbol

**Context**: Could allow per-symbol time windows (e.g., "TSLA ok after 10 AM, SPY ok all day").
**Decision**: Global time windows for all symbols: no-entry 9:30-10:00, cautious 11:30-14:00.
**Why**: Opening chop and mid-day low volume affect all equities similarly. Per-symbol config adds complexity without proportional benefit.
**Trade-off**: Cannot customize for specific symbols (e.g., futures open at different times).

## Decision 5: LMT for entries, MKT for exits and emergencies

**Context**: Could use LMT for everything.
**Decision**: LMT for entry orders. MKT for SL/TP exits and manual close.
**Why**: Entries are planned and patient — a few cents of slippage matters. Exits must be fast — if SL is hit, you want out NOW, not hoping for a fill.
**Trade-off**: LMT entry might not fill if price gaps away. Mitigation: LMT within 0.1% of current price, with fallback to MKT after 30s if needed (future enhancement).

## Decision 6: Slippage buffer reduces size, not adjusts SL

**Context**: Could widen SL to account for slippage.
**Decision**: Reduce position size so that `size * slippage_adjusted_stop = max_risk_usd`.
**Why**: Wider SL means lower win rate (price has more room to wander). Smaller size preserves the same dollar risk while maintaining a tighter, more honest stop.
**Trade-off**: Smaller position = smaller absolute profit. But better risk-adjusted returns.
