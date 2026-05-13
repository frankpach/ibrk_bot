# PRD: risk-engine-v2

## Overview

Enhance the risk engine of IBKR AI Trader with adaptive position sizing, trailing stops, market regime detection, time-of-day filtering, and slippage awareness.

## Requirements

### REQ-01: PositionSizer (Dynamic Sizing)

Formula:
```
base_size = max_risk_usd / (stop_loss_pct + slippage_buffer)
win_rate_adj = 0.5 + win_rate          # 0.65 WR → 1.15x
volatility_adj = 2.0 / atr_pct         # 4% ATR → 0.5x
confidence_adj = min(score / 75, 1.5)  # 90 score → 1.2x
final_size = base_size * win_rate_adj * volatility_adj * confidence_adj
capped_size = min(final_size, MAX_POSITION_USD / price)
```

- `slippage_buffer` = `SLIPPAGE_BUFFER = 0.005` (0.5% default, configurable).
- `win_rate` from `SymbolParameter.win_rate` (default 0.5 if < 5 trades).
- `atr_pct` from `FeatureSet.atr_pct`.
- `score` from `AnalysisResult.score.total`.
- Result must never exceed `MAX_POSITION_USD` or `capital * MAX_RISK_PCT / sl`.

**AC-01.1**: NVDA, price=$214, SL=2.5%, ATR=2.8%, win_rate=65%, score=78 → size ≈ 0.53 shares.
**AC-01.2**: SPY, price=$500, SL=2.5%, ATR=1.2%, win_rate=55%, score=72 → size ≈ 0.85 shares.
**AC-01.3**: Size with slippage buffer < size without buffer (always more conservative).

### REQ-02: TrailingStopManager

Rules:
1. **Breakeven Rule**: If P&L% > 1.5 × original_stop_loss_pct:
   - Move SL to `entry_price * (1 ± 0.003)` (breakeven + 0.3% buffer).
2. **Trailing Rule**: If P&L% > 3.0 × original_stop_loss_pct:
   - Trailing stop at 50% of max unrealized gain from entry.
   - `trailing_stop = entry_price + (max_price - entry_price) * 0.5` (for BUY).
3. Never move SL backward (worsen the stop).
4. Compute dynamically in `check_positions()` — no DB schema change.

**AC-02.1**: Trade entry $100, SL $97.5 (-2.5%). Price reaches $104 (+4% > 3.75%). SL moves to $100.3.
**AC-02.2**: Price reaches $110 (+10% > 7.5%). Trailing activates at $105. Price drops to $104.9 → position closes.
**AC-02.3**: SL never moves backward. If trailing_stop calculates below current SL, keep current SL.

### REQ-03: MarketRegimeDetector

- Source: VIX daily close via `IBDataLayer.get_ohlcv("VIX", "5 D", "1 day")`.
- Regimes:
  - `low_vol`: VIX < 15 → size_mult=1.2, sl_mult=0.9, entry_ok=True
  - `normal`: 15 ≤ VIX < 25 → size_mult=1.0, sl_mult=1.0, entry_ok=True
  - `high_vol`: 25 ≤ VIX < 35 → size_mult=0.5, sl_mult=1.3, entry_ok=True
  - `crisis`: VIX ≥ 35 → size_mult=0.0, sl_mult=1.5, entry_ok=False
- Checked before every entry.
- Checked every 15 minutes for regime changes.
- If regime changes to `high_vol`: widen existing SLs by 30% (one-time adjustment).
- If regime changes to `crisis`: notify user, block all new entries.

**AC-03.1**: VIX=32 → entry blocked? No (high_vol allows entry with reduced size).
**AC-03.2**: VIX=38 → entry blocked? Yes (crisis).
**AC-03.3**: Regime change normal→high_vol → existing position SL widened once.

### REQ-04: TimeFilter

- No entries during: 9:30-10:00 ET (opening chop).
- Reduced size during: 11:30-14:00 ET (mid-day low volume, size_mult=0.8).
- No entries: weekends (already handled by market hours).
- No entries: market holidays (optional, use holiday list or skip if no data).

**AC-04.1**: 9:35 ET → `is_entry_allowed()` returns `(False, "opening_chop")`.
**AC-04.2**: 10:05 ET → returns `(True, "ok")`.
**AC-04.3**: 12:00 ET → returns `(True, "mid_day_reduced")` and sizer applies 0.8x.

### REQ-05: SlippageEstimator

- Estimate slippage from bid-ask spread if available.
- Fallback: `SLIPPAGE_BUFFER = 0.005` (0.5%) if spread unavailable.
- Applied to position size calculation (REQ-01), not to SL directly.

**AC-05.1**: Spread data available for NVDA (0.3%) → slippage_buffer = 0.003.
**AC-05.2**: No spread data → uses default 0.005.

### REQ-06: LMT Orders for Entry

- `orders_preview` and `orders_place` default to `LMT` for entry.
- Limit price = current_price ± `slippage_buffer * current_price` (±0.5% for BUY/SELL).
- MKT still used for: SL exits, TP exits, manual close, emergency close.
- If LMT doesn't fill within 60s, fall back to MKT (future enhancement, not required for v1).

**AC-06.1**: BUY order at $214.91 with slippage 0.5% → LMT at $215.99.
**AC-06.2**: SELL order at $214.91 with slippage 0.5% → LMT at $213.84.

### REQ-07: Integration with Existing validate_order()

- `validate_order()` must call `TimeFilter.is_entry_allowed()` before approving.
- `validate_order()` must call `MarketRegimeDetector.get_regime()` and reject if `entry_ok=False`.
- `validate_order()` must use `PositionSizer.calculate_size()` instead of direct formula.
- All existing validations (symbol, capital, hours) continue working.

**AC-07.1**: Entry at 9:35 ET → validate_order returns rejected with reason "opening_chop".
**AC-07.2**: Entry during crisis (VIX=40) → rejected with reason "market_crisis".
**AC-07.3**: Entry at 10:05 ET, VIX=18 → approved with dynamically calculated size.

## Performance

- Position size calculation: < 1ms.
- Trailing stop check: < 1ms per position.
- VIX fetch: cached via IBDataLayer (TTL 900s).

## Security

- No new attack surface. All calculations are local.
- Frank can override with `/forzar_entrada SYMBOL` (bypasses time and regime filters).

## Open Questions

- Should trailing stop parameters be per-symbol learned via post-mortem? (Deferred.)
- Should regime detection use more than VIX? (Deferred to v2.)
