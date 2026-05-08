# Capital Liquidity Check & Order Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prevent orders from being placed when buying_power < estimated order cost, fix the broken LMT order path, and correct the position_size_units formula in the validator.

**Architecture:** Three targeted fixes: (1) pre-flight buying_power check in /orders/place and /orders/preview using real IB account data, (2) wire limit_price through the full order chain for LMT orders, (3) fix position_size_units formula to divide by price. Each fix is independent and tested in isolation.

**Tech Stack:** Python 3.13, ib_insync, FastAPI, SQLite (WAL), pytest

**Depends on:** Can be implemented independently of Plans A and B, but should be merged before going live.

---

## Task C1: Fix `position_size_units` in `validator.py`

**File to modify:** `app/risk/validator.py`
**Test file:** `tests/risk/test_validator_position_size.py`

### C1.1 — Read current validator signature

- [ ] Read `app/risk/validator.py` and note the full signature of `validate_order()` and how `position_size_units` is currently computed.

### C1.2 — Apply the fix

- [ ] Add `price: float = 1.0` as the last keyword parameter to `validate_order()`.
- [ ] Replace the current line:
  ```python
  position_size_units = int(max_position_usd)
  ```
  with:
  ```python
  position_size_units = int(max_position_usd / price) if price > 0 else 0
  ```
- [ ] Verify no other callers inside `app/` pass a positional argument at the position that would conflict (all call sites must still work with the default `price=1.0`).

### C1.3 — Write tests

- [ ] Create `tests/risk/test_validator_position_size.py` with the following complete content:

```python
"""Tests for position_size_units formula fix in validate_order().

Covers: correct division by price, zero-price guard, backward compatibility,
and crypto edge case (price > max_position).
"""
import pytest
from datetime import datetime
from app.risk.validator import validate_order


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _call(price: float, capital: float = 10_000.0, stop_loss_pct: float = 0.02):
    """Call validate_order with minimal required args and a given price."""
    return validate_order(
        symbol="AAPL",
        action="BUY",
        quantity=1,
        order_type="MKT",
        stop_loss_pct=stop_loss_pct,
        capital=capital,
        active_positions=0,
        now=datetime(2025, 6, 10, 14, 0, 0),   # Tuesday 14:00 — liquid hours
        price=price,
    )


# ---------------------------------------------------------------------------
# C1-T1: units = max_position_usd / price
# ---------------------------------------------------------------------------

def test_position_size_units_divides_by_price():
    """With max_position_usd ~= $200 and price=$50, units should be 4."""
    # Use capital and stop_loss_pct values that produce a known max_position_usd.
    # The validator computes:
    #   max_risk_usd  = capital * MAX_RISK_PCT   (or MIN_RISK_USD if larger)
    #   max_position_usd = min(max_risk_usd / stop_loss_pct, MAX_POSITION_USD)
    # We keep capital small so that max_position_usd stays below MAX_POSITION_USD.
    # With capital=$1000, MAX_RISK_PCT=0.02, stop_loss_pct=0.10:
    #   max_risk_usd  = max(1000 * 0.02, MIN_RISK_USD) = 20   (assuming MIN_RISK_USD <= 20)
    #   max_position_usd = 20 / 0.10 = 200
    # At price=$50 -> units = int(200 / 50) = 4
    result = validate_order(
        symbol="AAPL",
        action="BUY",
        quantity=4,
        order_type="MKT",
        stop_loss_pct=0.10,
        capital=1_000.0,
        active_positions=0,
        now=datetime(2025, 6, 10, 14, 0, 0),
        price=50.0,
    )
    assert result.position_size_units == 4, (
        f"Expected 4 units at $50 with $200 max_position, got {result.position_size_units}"
    )


# ---------------------------------------------------------------------------
# C1-T2: price=0 must not raise ZeroDivisionError
# ---------------------------------------------------------------------------

def test_position_size_units_zero_when_price_zero():
    """price=0 should yield units=0, never a ZeroDivisionError."""
    result = _call(price=0.0)
    assert result.position_size_units == 0


# ---------------------------------------------------------------------------
# C1-T3: backward compatibility — calling without price= defaults to 1.0
# ---------------------------------------------------------------------------

def test_position_size_units_backward_compat():
    """Omitting price= should behave as if price=1.0 (old behavior preserved)."""
    result_no_price = validate_order(
        symbol="AAPL",
        action="BUY",
        quantity=1,
        order_type="MKT",
        stop_loss_pct=0.02,
        capital=10_000.0,
        active_positions=0,
        now=datetime(2025, 6, 10, 14, 0, 0),
    )
    result_price_one = validate_order(
        symbol="AAPL",
        action="BUY",
        quantity=1,
        order_type="MKT",
        stop_loss_pct=0.02,
        capital=10_000.0,
        active_positions=0,
        now=datetime(2025, 6, 10, 14, 0, 0),
        price=1.0,
    )
    assert result_no_price.position_size_units == result_price_one.position_size_units


# ---------------------------------------------------------------------------
# C1-T4: BTC at $67 000 with $500 max_position -> 0 units (correct!)
# ---------------------------------------------------------------------------

def test_position_size_units_crypto_fractional():
    """BTC at $67 000 with a max_position < $67 000 should yield 0 integer units.

    This is correct behaviour: the caller is responsible for fractional qty
    handling (a separate concern). The validator must not return 1 spuriously.
    """
    # Drive capital low enough that max_position_usd is well below $67 000.
    # capital=$5 000, MAX_RISK_PCT=0.02, stop_loss_pct=0.02:
    #   max_risk_usd    = max(5000 * 0.02, ...) = 100
    #   max_position_usd = 100 / 0.02 = 5000
    # 5000 / 67000 = 0.074 -> int = 0  correct
    result = validate_order(
        symbol="BTC",
        action="BUY",
        quantity=0,
        order_type="MKT",
        stop_loss_pct=0.02,
        capital=5_000.0,
        active_positions=0,
        now=datetime(2025, 6, 10, 14, 0, 0),
        price=67_000.0,
    )
    assert result.position_size_units == 0, (
        f"Expected 0 BTC units (fractional, not handled here), got {result.position_size_units}"
    )
```

### C1.4 — Run tests

- [ ] Run `pytest tests/risk/test_validator_position_size.py -q` and confirm **4 passed**.

---

## Task C2: Buying power pre-flight in `app/api/main.py`

**File to modify:** `app/api/main.py`
**Test file:** `tests/api/test_orders_buying_power.py`

### C2.1 — Read the route handlers

- [ ] Read `app/api/main.py` and identify the exact lines in both `/orders/preview` and `/orders/place` where `units` is computed and where `client.place_order(...)` / preview response is built.

### C2.2 — Apply the fix to `/orders/preview`

- [ ] After the line `units = int(max_position_usd / current_price)` in the `/orders/preview` handler, insert:

```python
buying_power = account.get("buying_power", 0.0)
estimated_cost = units * current_price
if units == 0:
    raise HTTPException(
        status_code=400,
        detail=f"Position size is 0 units at ${current_price:.2f} — price too high for available capital",
    )
if estimated_cost > buying_power:
    raise HTTPException(
        status_code=400,
        detail=f"Insufficient buying power: need ${estimated_cost:.2f}, available ${buying_power:.2f}",
    )
```

### C2.3 — Apply the same fix to `/orders/place`

- [ ] Find the equivalent `units` computation in `/orders/place` and insert the identical block immediately after it (before the `client.place_order(...)` call).

### C2.4 — Write tests

- [ ] Create `tests/api/test_orders_buying_power.py` with the following complete content:

```python
"""Tests for buying power pre-flight checks in /orders/preview and /orders/place.

Uses FastAPI TestClient with fully mocked IBKRClient so no real IB connection
is needed.
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch

from app.api.main import app

client_test = TestClient(app)

# ---------------------------------------------------------------------------
# Shared mock factories
# ---------------------------------------------------------------------------

def _account(buying_power: float, net_liq: float = 500.0):
    return {
        "net_liquidation": net_liq,
        "buying_power": buying_power,
        "cash_balance": buying_power,
    }


def _preview_payload(symbol: str = "AAPL", order_type: str = "MKT"):
    return {
        "symbol": symbol,
        "action": "BUY",
        "quantity": 1,
        "order_type": order_type,
        "stop_loss_pct": 0.02,
        "take_profit_pct": 0.04,
    }


def _place_payload(symbol: str = "AAPL", order_type: str = "MKT"):
    return {
        "symbol": symbol,
        "action": "BUY",
        "quantity": 1,
        "order_type": order_type,
        "stop_loss_pct": 0.02,
        "take_profit_pct": 0.04,
    }


# ---------------------------------------------------------------------------
# C2-T1: /orders/preview rejects when buying_power is too low
# ---------------------------------------------------------------------------

def test_preview_rejects_when_insufficient_buying_power():
    """Mock buying_power=$10 but order costs ~$100 -> expect HTTP 400."""
    with patch("app.api.main.client") as mock_client:
        mock_client.get_stock_price.return_value = {"market_price": 100.0}
        mock_client.get_account.return_value = _account(buying_power=10.0)
        mock_client.get_portfolio.return_value = []

        resp = client_test.post("/orders/preview", json=_preview_payload())

    assert resp.status_code == 400
    assert "buying power" in resp.json()["detail"].lower()


# ---------------------------------------------------------------------------
# C2-T2: /orders/preview accepts when buying_power is sufficient
# ---------------------------------------------------------------------------

def test_preview_accepts_when_sufficient_buying_power():
    """Mock buying_power=$1 000 -> preview should succeed (HTTP 200)."""
    with patch("app.api.main.client") as mock_client:
        mock_client.get_stock_price.return_value = {"market_price": 100.0}
        mock_client.get_account.return_value = _account(
            buying_power=1_000.0, net_liq=1_000.0
        )
        mock_client.get_portfolio.return_value = []

        resp = client_test.post("/orders/preview", json=_preview_payload())

    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# C2-T3: /orders/place rejects when units == 0 (price too high for capital)
# ---------------------------------------------------------------------------

def test_place_rejects_when_zero_units():
    """Price=$1 000 000, capital=$500 -> units=0 -> expect HTTP 400 with '0 units'."""
    with patch("app.api.main.client") as mock_client:
        mock_client.get_stock_price.return_value = {"market_price": 1_000_000.0}
        mock_client.get_account.return_value = _account(
            buying_power=500.0, net_liq=500.0
        )
        mock_client.get_portfolio.return_value = []

        resp = client_test.post("/orders/place", json=_place_payload())

    assert resp.status_code == 400
    assert "0 units" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# C2-T4: /orders/place rejects when estimated_cost > buying_power
# ---------------------------------------------------------------------------

def test_place_rejects_when_buying_power_low():
    """Price=$100, buying_power=$10 -> estimated_cost=$100 > $10 -> HTTP 400."""
    with patch("app.api.main.client") as mock_client:
        mock_client.get_stock_price.return_value = {"market_price": 100.0}
        mock_client.get_account.return_value = _account(
            buying_power=10.0, net_liq=500.0
        )
        mock_client.get_portfolio.return_value = []

        resp = client_test.post("/orders/place", json=_place_payload())

    assert resp.status_code == 400
    assert "insufficient buying power" in resp.json()["detail"].lower()
```

### C2.5 — Run tests

- [ ] Run `pytest tests/api/test_orders_buying_power.py -q` and confirm **4 passed**.

---

## Task C3: Fix LMT orders — add `limit_price` field and wire through client

**Files to modify:**
- `app/api/main.py` — `OrderPreviewRequest` Pydantic model + both route handlers
- `app/ibkr/client.py` — `place_order` / `_place_order_async`

**Test file:** `tests/ibkr/test_lmt_order.py`

### C3.1 — Read the Pydantic model and client

- [ ] Read `app/api/main.py` to find the `OrderPreviewRequest` (and `OrderPlaceRequest` if separate).
- [ ] Read `app/ibkr/client.py` to find `place_order` and note where `ib_insync.LimitOrder` or `ib_insync.Order` is constructed.

### C3.2 — Add `limit_price` to request model(s)

- [ ] In `OrderPreviewRequest` (and `OrderPlaceRequest` / `OrderRequest` if they are distinct classes), add:
  ```python
  limit_price: float | None = None
  ```
  This field is optional so that existing MKT-only callers are unaffected.

### C3.3 — Pass `limit_price` through route handlers

- [ ] In `/orders/preview`, extract `limit_price = req.limit_price` and pass it to any validator or preview-result builder that constructs a notional order object.
- [ ] In `/orders/place`, extract `limit_price = req.limit_price` and pass it into `client.place_order(...)`.

### C3.4 — Wire `limit_price` into `client.place_order`

- [ ] In `app/ibkr/client.py`, update `place_order` (and `_place_order_async` if it exists) to accept `limit_price: float | None = None`.
- [ ] Inside the function, after the `Order` (or `LimitOrder`) object is constructed, add:
  ```python
  if order_type.upper() == "LMT":
      if limit_price is None:
          raise ValueError("limit_price is required for LMT orders")
      order.lmtPrice = float(limit_price)
  ```
  If ib_insync's `LimitOrder` helper is used instead of a raw `Order`, replace the constructor call with `LimitOrder(action, quantity, limit_price)` and remove the manual assignment.

### C3.5 — Write tests

- [ ] Create `tests/ibkr/test_lmt_order.py` with the following complete content:

```python
"""Tests for LMT order wiring in IBKRClient.place_order.

Verifies that lmtPrice is set correctly for LMT orders and absent for MKT,
and that the Pydantic request model accepts the limit_price field.
"""
import pytest
from unittest.mock import MagicMock, patch

from app.ibkr.client import IBKRClient
from app.api.main import OrderPreviewRequest


# ---------------------------------------------------------------------------
# C3-T1: LMT order sets lmtPrice on the ib_insync order object
# ---------------------------------------------------------------------------

def test_lmt_order_sets_lmt_price():
    """place_order with order_type='LMT' and limit_price=150.0 must set lmtPrice=150.0."""
    c = IBKRClient.__new__(IBKRClient)
    c.ib = MagicMock()

    trade = MagicMock()
    trade.order.orderId = 1
    trade.orderStatus.status = "Submitted"
    c.ib.placeOrder = MagicMock(return_value=trade)

    # Some implementations also call ib.qualifyContracts -- mock it away.
    c.ib.qualifyContracts = MagicMock(return_value=[MagicMock()])

    c.place_order("AAPL", "BUY", 5, "LMT", limit_price=150.0)

    assert c.ib.placeOrder.called, "ib.placeOrder was never called"
    placed_order = c.ib.placeOrder.call_args[0][1]   # second positional arg = order
    assert placed_order.lmtPrice == 150.0, (
        f"Expected lmtPrice=150.0, got {getattr(placed_order, 'lmtPrice', 'NOT SET')}"
    )


# ---------------------------------------------------------------------------
# C3-T2: MKT order does NOT set lmtPrice
# ---------------------------------------------------------------------------

def test_mkt_order_does_not_set_lmt_price():
    """place_order with order_type='MKT' must NOT set lmtPrice (or leave it as 0/None)."""
    c = IBKRClient.__new__(IBKRClient)
    c.ib = MagicMock()

    trade = MagicMock()
    trade.order.orderId = 2
    trade.orderStatus.status = "Submitted"
    c.ib.placeOrder = MagicMock(return_value=trade)
    c.ib.qualifyContracts = MagicMock(return_value=[MagicMock()])

    c.place_order("AAPL", "BUY", 5, "MKT")

    assert c.ib.placeOrder.called
    placed_order = c.ib.placeOrder.call_args[0][1]
    lmt = getattr(placed_order, "lmtPrice", None)
    # ib_insync initialises lmtPrice to 0.0 by default for a raw Order().
    # Either 0.0 or None is acceptable for a MKT order; 150.0 is not.
    assert lmt != 150.0, "lmtPrice should not be set to a price value for MKT orders"


# ---------------------------------------------------------------------------
# C3-T3: OrderPreviewRequest Pydantic model accepts limit_price
# ---------------------------------------------------------------------------

def test_preview_request_accepts_limit_price():
    """OrderPreviewRequest must parse limit_price without validation errors."""
    req = OrderPreviewRequest(
        symbol="AAPL",
        action="BUY",
        quantity=1,
        order_type="LMT",
        stop_loss_pct=0.02,
        take_profit_pct=0.04,
        limit_price=150.0,
    )
    assert req.limit_price == 150.0


def test_preview_request_limit_price_optional():
    """limit_price must be optional (defaults to None) for backward compatibility."""
    req = OrderPreviewRequest(
        symbol="AAPL",
        action="BUY",
        quantity=1,
        order_type="MKT",
        stop_loss_pct=0.02,
        take_profit_pct=0.04,
    )
    assert req.limit_price is None
```

> **Note:** The test file contains 4 tests (including the optional backward-compat one for `limit_price=None`). The acceptance criteria counts 3; all 4 should pass.

### C3.6 — Run tests

- [ ] Run `pytest tests/ibkr/test_lmt_order.py -q` and confirm **all passed** (3-4 tests).

---

## Integration & Full-Suite Verification

### INT-1 — Run all three new test files together

- [ ] Run:
  ```bash
  pytest tests/risk/test_validator_position_size.py \
         tests/api/test_orders_buying_power.py \
         tests/ibkr/test_lmt_order.py \
         -v
  ```
  Expected: **11+ passed, 0 failed**.

### INT-2 — Run the full test suite

- [ ] Run `pytest -q` from the project root.
- [ ] Confirm no pre-existing tests were broken by the changes.
- [ ] If any pre-existing tests fail because of the new `price` parameter signature, update those call sites to pass `price=` explicitly or rely on the default.

### INT-3 — Manual smoke test (LMT order preview)

- [ ] Start the FastAPI server: `uvicorn app.api.main:app --port 8088 --reload`
- [ ] Run:
  ```bash
  curl -s -X POST http://127.0.0.1:8088/orders/preview \
    -H "Content-Type: application/json" \
    -d '{
      "symbol": "AAPL",
      "action": "BUY",
      "quantity": 1,
      "order_type": "LMT",
      "stop_loss_pct": 0.02,
      "take_profit_pct": 0.04,
      "limit_price": 150.0
    }' | python3 -m json.tool
  ```
- [ ] Confirm the response contains `"approved": true` (or equivalent) and reflects `limit_price: 150.0` in the order details.

### INT-4 — Manual smoke test (insufficient buying power)

- [ ] With the server running and IB Gateway **disconnected** (or using a paper account with low buying power), attempt:
  ```bash
  curl -s -X POST http://127.0.0.1:8088/orders/preview \
    -H "Content-Type: application/json" \
    -d '{
      "symbol": "NVDA",
      "action": "BUY",
      "quantity": 1,
      "order_type": "MKT",
      "stop_loss_pct": 0.02,
      "take_profit_pct": 0.04
    }' | python3 -m json.tool
  ```
- [ ] If buying_power < estimated_cost, confirm HTTP 400 with `"Insufficient buying power"` detail.

---

## Acceptance Criteria

| Test command | Expected result |
|---|---|
| `pytest tests/risk/test_validator_position_size.py -q` | 4 passed |
| `pytest tests/api/test_orders_buying_power.py -q` | 4 passed |
| `pytest tests/ibkr/test_lmt_order.py -q` | 3-4 passed |
| `pytest -q` (full suite) | All pass, 0 regressions |
| Manual LMT preview curl | `approved` response, `limit_price` reflected |
| Manual low-capital curl | HTTP 400, "Insufficient buying power" in detail |

---

## Change Summary

| File | Change |
|---|---|
| `app/risk/validator.py` | Add `price: float = 1.0` param; fix `position_size_units` formula |
| `app/api/main.py` | Add `limit_price` to request model; add buying power pre-flight in both route handlers; pass `limit_price` to `client.place_order` |
| `app/ibkr/client.py` | Accept `limit_price` param; set `order.lmtPrice` for LMT orders |
| `tests/risk/test_validator_position_size.py` | New — 4 tests for formula fix |
| `tests/api/test_orders_buying_power.py` | New — 4 tests for buying power check |
| `tests/ibkr/test_lmt_order.py` | New — 4 tests for LMT wiring |
