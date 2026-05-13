# Interface Design: risk-engine-v2

## Chosen Alternative

**Alternative A: Depth-first** — minimal surface, maximum behavior.

**Why**: El motor de riesgo es infraestructura crítica. Debe ser robusto, predecible, y fácil de auditar. Alternative B (user-first) habría priorizado comandos Telegram, pero las decisiones de riesgo deben ser automáticas y determinísticas. Alternative C (reusability-first) habría agregado abstracciones genéricas que complican el código para un solo sistema.

## Primary Interface

```python
# Dynamic position sizing
class PositionSizer:
    def calculate_size(
        self,
        symbol: str,
        entry_price: float,
        stop_loss_pct: float,
        capital: float,
        atr_pct: float | None = None,
        win_rate: float | None = None,
        score: float | None = None,
    ) -> PositionSizeResult: ...

@dataclass
class PositionSizeResult:
    units: float
    estimated_risk_usd: float
    estimated_slippage_usd: float
    reasons: list[str]

# Trailing stop management
class TrailingStopManager:
    def update_stop_levels(
        self,
        trade: Trade,
        current_price: float,
    ) -> StopUpdateResult: ...

@dataclass
class StopUpdateResult:
    new_stop_price: float | None   # None if no change
    reason: str | None             # "breakeven", "trailing", "none"
    should_close: bool             # True if current_price <= new_stop

# Market regime
class MarketRegimeDetector:
    def get_regime(self) -> MarketRegime: ...
    def get_adjustments(self) -> RegimeAdjustments: ...

@dataclass
class MarketRegime:
    vix_level: float
    regime: Literal["low_vol", "normal", "high_vol", "crisis"]

@dataclass
class RegimeAdjustments:
    position_size_multiplier: float   # 1.0, 0.8, 0.5, 0.0
    sl_widening_multiplier: float     # 1.0, 1.0, 1.3, 1.5
    entry_blocked: bool               # False, False, False, True

# Time filter
class TimeFilter:
    def is_entry_allowed(self, now: datetime | None = None) -> tuple[bool, str]: ...
    # Returns (allowed, reason)

# Slippage estimation
class SlippageEstimator:
    def estimate_slippage_pct(self, symbol: str) -> float: ...
```

## Key Workflows

### Workflow 1: Adaptive Entry (Complete Flow)

1. Scanner detects signal.
2. `TimeFilter.is_entry_allowed()` → checks hour. If 9:32 AM → returns `(False, "opening_chop")`.
3. If allowed: `MarketRegimeDetector.get_regime()` → VIX=18 → `normal`.
4. `PositionSizer.calculate_size(symbol, price, sl_pct, capital, atr, win_rate, score)`:
   - Base size = max_risk / (sl_pct + slippage_buffer)
   - Apply multipliers: win_rate, volatility, confidence
   - Result: 0.53 shares of NVDA
5. `validate_order()` checks: size > 0, within limits, regime allows entry.
6. Order placed as LMT (not MKT).

### Workflow 2: Position Protection (Trailing Stop)

1. `check_positions()` runs every 2 minutes.
2. For each open trade, fetch current price.
3. `TrailingStopManager.update_stop_levels(trade, current_price)`:
   - Calculate P&L% from entry.
   - If P&L% > 1.5 × original_SL% → breakeven trigger.
   - If P&L% > 3.0 × original_SL% → trailing trigger at 50% of max gain.
4. If `new_stop_price` != current stop: log and update (in memory).
5. If `current_price <= new_stop_price`: close position immediately.
6. Notify user: "{symbol}: trailing stop triggered at ${price}. P&L: +{pct}%"

### Workflow 3: Market Regime Change

1. APScheduler job checks VIX every 15 minutes.
2. `MarketRegimeDetector.get_regime()` → VIX jumps from 18 to 32.
3. Regime changes from `normal` to `high_vol`.
4. Adjustments applied:
   - New entries: size × 0.5, SL × 1.3
   - Existing positions: SL widened by 30% to avoid noise stops
5. Notification: "⚠️ Régimen cambiado a ALTA VOLATILIDAD (VIX 32). Nuevas entradas reducidas 50%. SLs ampliados."

## Components to Build

- `PositionSizer` (new)
- `TrailingStopManager` (new)
- `MarketRegimeDetector` (new)
- `TimeFilter` (new)
- `SlippageEstimator` (new)
- Updated `validate_order()` (extend)
- Updated `check_positions()` (extend)

## Components to Reuse/Extend

- `IBDataLayer.get_ohlcv("VIX")` for regime detection
- `SymbolParameter` table for per-symbol win rates
- `Trade` model (read-only for trailing stop calc)
- `validate_order()` from `risk/validator.py`

## Events to Publish

- None (internal module)

## Events to Consume

- None (internal module)

## Trade-offs Made

- **Optimizing for**: Risk-adjusted returns and capital preservation.
- **Sacrificing**: Maximum position size (slippage buffer reduces it). Entry frequency (time filter blocks some). Simplicity (more rules to understand).
- **Why this is the right choice**: A $500 account cannot afford catastrophic losses. Protecting capital is more important than maximizing trades.
