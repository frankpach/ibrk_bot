# IBKR AI Swing Trader — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Construir un sistema de swing trading semi-autónomo en Raspberry Pi que usa Kimi K2 para tomar decisiones de compra/venta, con motor de riesgo determinístico, preprocesador de señales técnicas, y aprendizaje por post-mortem.

**Architecture:** FastAPI como núcleo REST en puerto 8088, IBKRClient thread-safe como capa de acceso a IB Gateway, preprocesador que corre sin LLM y despierta al agente Kimi K2 solo cuando hay señal STRONG o MEDIUM. SQLite para persistencia de trades, patrones y señales.

**Tech Stack:** Python 3.13, FastAPI, ib_insync, SQLite, pandas, openai SDK (Kimi K2), python-telegram-bot, APScheduler, pytz

---

## Mapa de Archivos

```
~/ibkr-bot/
├── app/
│   ├── config/settings.py           MODIFICAR
│   ├── ibkr/client.py               MODIFICAR — agregar get_account, get_portfolio, place_order, cancel_order
│   ├── risk/validator.py            CREAR — motor de riesgo determinístico
│   ├── db/
│   │   ├── __init__.py              CREAR
│   │   ├── database.py              CREAR — conexión SQLite + CRUD
│   │   └── models.py                CREAR — dataclasses
│   ├── scanner/
│   │   ├── __init__.py              CREAR
│   │   └── preprocessor.py          CREAR — scheduler de señales técnicas
│   ├── llm/
│   │   ├── __init__.py              CREAR
│   │   └── agent.py                 CREAR — agente Kimi K2 con tool use
│   ├── positions/
│   │   ├── __init__.py              CREAR
│   │   └── manager.py               CREAR — daemon stop-loss/take-profit
│   └── api/main.py                  MODIFICAR — todos los endpoints
├── tests/
│   ├── test_risk_validator.py       CREAR
│   ├── test_ibkr_client.py          CREAR
│   └── test_preprocessor.py         CREAR
├── run.py                           CREAR — orquestador principal
├── .env                             CREAR
└── requirements.txt                 CREAR
```

---

## FASE 1: Estabilizar API + Motor de Riesgo

### Task 1: Actualizar settings.py y crear requirements.txt

**Files:**
- Modify: `app/config/settings.py`
- Create: `requirements.txt`
- Create: `.env`

- [ ] **Step 1: Reemplazar settings.py**

```python
# app/config/settings.py
import os
from zoneinfo import ZoneInfo

IB_HOST = "127.0.0.1"
IB_PORT = 4002
IB_CLIENT_ID = 10
MARKET_DATA_TYPE = 3  # 3=delayed, 1=live

READ_ONLY = True
PAPER_TRADING_ONLY = True
REQUIRE_HUMAN_APPROVAL = False  # False en paper, True en live
MAX_POSITIONS = 3
MAX_RISK_PCT = 0.02
MIN_RISK_USD = 2.0

ALLOWED_SYMBOLS = [
    "AAPL", "MSFT", "SPY", "QQQ",
    "TSLA", "NVDA", "AMZN", "GOOGL",
    "META", "JPM",
]

LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.moonshot.cn/v1")
LLM_MODEL = os.getenv("LLM_MODEL", "moonshot-v1-8k")
LLM_API_KEY = os.getenv("LLM_API_KEY", "")

SCAN_INTERVAL_MINUTES = 15
MARKET_TZ = ZoneInfo("America/New_York")
MARKET_OPEN_HOUR = 9
MARKET_OPEN_MINUTE = 15
MARKET_CLOSE_HOUR = 16
MARKET_CLOSE_MINUTE = 15

POSITION_CHECK_MINUTES = 2
MIN_PROFIT_PCT_MEDIUM = 0.01  # 1% minimo para cerrar senal MEDIUM

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
TELEGRAM_APPROVAL_TIMEOUT_SECONDS = 300

DB_PATH = os.getenv("DB_PATH", "ibkr_trader.db")
```

- [ ] **Step 2: Crear .env**

```
LLM_API_KEY=tu_api_key_de_kimi
LLM_BASE_URL=https://api.moonshot.cn/v1
LLM_MODEL=moonshot-v1-8k
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
DB_PATH=ibkr_trader.db
```

- [ ] **Step 3: Instalar dependencias**

```bash
cd ~/ibkr-bot && source .venv/bin/activate
pip install pandas APScheduler python-dotenv openai httpx pytest pytest-asyncio
pip freeze > requirements.txt
```

- [ ] **Step 4: Commit**

```bash
git add app/config/settings.py requirements.txt .env
git commit -m "feat: expand settings for full system config"
```

---

### Task 2: Agregar get_account y get_portfolio al IBKRClient

**Files:**
- Modify: `app/ibkr/client.py`
- Create: `tests/test_ibkr_client.py`

- [ ] **Step 1: Escribir tests primero**

```python
# tests/test_ibkr_client.py
import pytest
from app.ibkr.client import IBKRClient


@pytest.fixture(scope="module")
def client():
    c = IBKRClient()
    yield c
    c.disconnect()


def test_get_account_returns_expected_keys(client):
    account = client.get_account()
    assert "net_liquidation" in account
    assert "buying_power" in account
    assert "cash_balance" in account
    assert "currency" in account


def test_get_account_values_are_numeric(client):
    account = client.get_account()
    assert isinstance(account["net_liquidation"], float)
    assert account["net_liquidation"] > 0


def test_get_portfolio_returns_list(client):
    portfolio = client.get_portfolio()
    assert isinstance(portfolio, list)


def test_get_portfolio_item_keys(client):
    portfolio = client.get_portfolio()
    if portfolio:
        item = portfolio[0]
        assert "symbol" in item
        assert "quantity" in item
        assert "avg_cost" in item
        assert "market_value" in item
        assert "unrealized_pnl" in item
```

- [ ] **Step 2: Correr test para verificar que falla**

```bash
cd ~/ibkr-bot && source .venv/bin/activate
pytest tests/test_ibkr_client.py -v
```
Esperado: `AttributeError: 'IBKRClient' object has no attribute 'get_account'`

- [ ] **Step 3: Agregar metodos al final de IBKRClient en client.py**

```python
    async def _get_account_async(self) -> dict:
        await self._connect_async()
        summary = self.ib.accountSummary()
        result = {"net_liquidation": 0.0, "buying_power": 0.0, "cash_balance": 0.0, "currency": "USD"}
        for item in summary:
            if item.tag == "NetLiquidation":
                result["net_liquidation"] = float(item.value)
                result["currency"] = item.currency
            elif item.tag == "BuyingPower":
                result["buying_power"] = float(item.value)
            elif item.tag == "TotalCashValue":
                result["cash_balance"] = float(item.value)
        return result

    def get_account(self) -> dict:
        with self._lock:
            return self._run_sync(self._get_account_async())

    async def _get_portfolio_async(self) -> list:
        await self._connect_async()
        items = self.ib.portfolio()
        return [
            {
                "symbol": item.contract.symbol,
                "quantity": item.position,
                "avg_cost": item.averageCost,
                "market_value": item.marketValue,
                "unrealized_pnl": item.unrealizedPNL,
            }
            for item in items
        ]

    def get_portfolio(self) -> list:
        with self._lock:
            return self._run_sync(self._get_portfolio_async())
```

- [ ] **Step 4: Correr tests**

```bash
pytest tests/test_ibkr_client.py -v
```
Esperado: todos PASS

- [ ] **Step 5: Commit**

```bash
git add app/ibkr/client.py tests/test_ibkr_client.py
git commit -m "feat: add get_account and get_portfolio to IBKRClient"
```

---

### Task 3: Crear motor de riesgo (validator.py)

**Files:**
- Create: `app/risk/validator.py`
- Create: `tests/test_risk_validator.py`

- [ ] **Step 1: Escribir tests**

```python
# tests/test_risk_validator.py
from datetime import datetime
from zoneinfo import ZoneInfo
from app.risk.validator import validate_order

ET = ZoneInfo("America/New_York")


def market_open():
    return datetime(2026, 5, 5, 10, 0, 0, tzinfo=ET)  # martes 10am


def market_closed():
    return datetime(2026, 5, 9, 10, 0, 0, tzinfo=ET)  # sabado


def test_rejects_unknown_symbol():
    r = validate_order("FAKE", "BUY", 1, "MKT", 0.02, 1000.0, 0, market_open())
    assert r.approved is False
    assert any("not allowed" in x for x in r.reasons)


def test_rejects_too_many_positions():
    r = validate_order("AAPL", "BUY", 1, "MKT", 0.02, 1000.0, 3, market_open())
    assert r.approved is False
    assert any("positions" in x for x in r.reasons)


def test_rejects_invalid_order_type():
    r = validate_order("AAPL", "BUY", 1, "STOP", 0.02, 1000.0, 0, market_open())
    assert r.approved is False
    assert any("order type" in x for x in r.reasons)


def test_rejects_outside_market_hours():
    r = validate_order("AAPL", "BUY", 1, "MKT", 0.02, 1000.0, 0, market_closed())
    assert r.approved is False
    assert any("market hours" in x for x in r.reasons)


def test_approves_valid_order():
    r = validate_order("AAPL", "BUY", 1, "MKT", 0.02, 1000.0, 0, market_open())
    assert r.approved is True
    assert r.estimated_risk_usd <= 20.0


def test_min_risk_when_capital_below_100():
    r = validate_order("AAPL", "BUY", 1, "MKT", 0.02, 50.0, 0, market_open())
    assert r.approved is True
    assert r.estimated_risk_usd >= 2.0


def test_returns_position_size():
    r = validate_order("AAPL", "BUY", 1, "MKT", 0.025, 1000.0, 0, market_open())
    assert r.approved is True
    assert r.position_size_units > 0
```

- [ ] **Step 2: Correr tests — verificar que fallan**

```bash
pytest tests/test_risk_validator.py -v
```
Esperado: `ModuleNotFoundError: No module named 'app.risk.validator'`

- [ ] **Step 3: Crear app/risk/validator.py**

```python
# app/risk/validator.py
from dataclasses import dataclass, field
from datetime import datetime
from zoneinfo import ZoneInfo

from app.config.settings import (
    ALLOWED_SYMBOLS, MAX_POSITIONS, MAX_RISK_PCT, MIN_RISK_USD,
    MARKET_TZ, MARKET_OPEN_HOUR, MARKET_CLOSE_HOUR,
)

ALLOWED_ORDER_TYPES = {"MKT", "LMT"}


@dataclass
class ValidationResult:
    approved: bool
    reasons: list[str] = field(default_factory=list)
    position_size_units: int = 0
    estimated_risk_usd: float = 0.0


def validate_order(
    symbol: str, action: str, quantity: int, order_type: str,
    stop_loss_pct: float, capital: float, active_positions: int,
    now: datetime | None = None,
) -> ValidationResult:
    if now is None:
        now = datetime.now(tz=MARKET_TZ)

    reasons = []

    if symbol.upper() not in ALLOWED_SYMBOLS:
        reasons.append(f"Symbol {symbol} is not allowed")

    if active_positions >= MAX_POSITIONS:
        reasons.append(f"Max positions ({MAX_POSITIONS}) already active")

    if order_type.upper() not in ALLOWED_ORDER_TYPES:
        reasons.append(f"Invalid order type {order_type}. Allowed: {ALLOWED_ORDER_TYPES}")

    if not _is_market_hours(now):
        reasons.append("Outside market hours (09:30-16:00 ET, Mon-Fri)")

    max_risk_usd = max(capital * MAX_RISK_PCT, MIN_RISK_USD)
    max_position_usd = max_risk_usd / stop_loss_pct if stop_loss_pct > 0 else 0
    position_size_units = int(max_position_usd)
    estimated_risk_usd = position_size_units * stop_loss_pct

    if reasons:
        return ValidationResult(approved=False, reasons=reasons)

    return ValidationResult(
        approved=True,
        reasons=["Order validated. Execution requires /orders/place"],
        position_size_units=position_size_units,
        estimated_risk_usd=round(estimated_risk_usd, 2),
    )


def _is_market_hours(now: datetime) -> bool:
    et = now.astimezone(MARKET_TZ)
    if et.weekday() >= 5:
        return False
    open_t = et.replace(hour=9, minute=30, second=0, microsecond=0)
    close_t = et.replace(hour=16, minute=0, second=0, microsecond=0)
    return open_t <= et <= close_t
```

- [ ] **Step 4: Correr tests**

```bash
pytest tests/test_risk_validator.py -v
```
Esperado: todos PASS

- [ ] **Step 5: Commit**

```bash
git add app/risk/validator.py tests/test_risk_validator.py
git commit -m "feat: add deterministic risk validator"
```

---

### Task 4: Completar endpoints en main.py

**Files:**
- Modify: `app/api/main.py`

- [ ] **Step 1: Reemplazar main.py completo**

```python
# app/api/main.py
from datetime import datetime
from pydantic import BaseModel
from fastapi import FastAPI, HTTPException

from app.config.settings import ALLOWED_SYMBOLS, MARKET_TZ, MAX_RISK_PCT, MIN_RISK_USD
from app.ibkr.client import IBKRClient
from app.risk.validator import validate_order

app = FastAPI(title="IBKR AI Trader API")
client = IBKRClient()


class OrderPreviewRequest(BaseModel):
    symbol: str
    action: str
    quantity: int
    order_type: str
    stop_loss_pct: float
    take_profit_pct: float


class SymbolProposalRequest(BaseModel):
    symbol: str
    reason: str


@app.get("/health")
def health():
    return {"status": "ok", "connected": client.ib.isConnected()}


@app.get("/price/{symbol}")
def get_price(symbol: str):
    symbol = symbol.upper()
    if symbol not in ALLOWED_SYMBOLS:
        raise HTTPException(status_code=403, detail=f"Symbol {symbol} not allowed")
    try:
        return client.get_stock_price(symbol)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/account")
def get_account():
    try:
        return client.get_account()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/portfolio")
def get_portfolio():
    try:
        return client.get_portfolio()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/allowed-symbols")
def get_allowed_symbols():
    return {"symbols": ALLOWED_SYMBOLS}


@app.post("/symbols/propose")
def propose_symbol(req: SymbolProposalRequest):
    return {
        "status": "pending_approval",
        "symbol": req.symbol.upper(),
        "reason": req.reason,
        "message": "Symbol proposal logged. Awaiting human approval.",
    }


@app.post("/orders/preview")
def orders_preview(req: OrderPreviewRequest):
    symbol = req.symbol.upper()
    try:
        price_data = client.get_stock_price(symbol)
        current_price = price_data["market_price"]
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Could not fetch price: {exc}")
    try:
        account = client.get_account()
        capital = account["net_liquidation"]
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Could not fetch account: {exc}")
    try:
        portfolio = client.get_portfolio()
        active_positions = len(portfolio)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Could not fetch portfolio: {exc}")

    result = validate_order(
        symbol=symbol, action=req.action, quantity=req.quantity,
        order_type=req.order_type, stop_loss_pct=req.stop_loss_pct,
        capital=capital, active_positions=active_positions,
        now=datetime.now(tz=MARKET_TZ),
    )

    max_risk_usd = max(capital * MAX_RISK_PCT, MIN_RISK_USD)
    max_position_usd = max_risk_usd / req.stop_loss_pct if req.stop_loss_pct > 0 else 0
    units = int(max_position_usd / current_price) if current_price > 0 else 0
    estimated_risk = units * current_price * req.stop_loss_pct
    estimated_value = units * current_price

    return {
        "approved": result.approved,
        "requires_human_approval": False,
        "symbol": symbol,
        "action": req.action,
        "current_price": current_price,
        "recommended_units": units,
        "estimated_value": round(estimated_value, 2),
        "estimated_risk_usd": round(estimated_risk, 2),
        "stop_loss_pct": req.stop_loss_pct,
        "take_profit_pct": req.take_profit_pct,
        "stop_loss_price": round(current_price * (1 - req.stop_loss_pct), 2),
        "take_profit_price": round(current_price * (1 + req.take_profit_pct), 2),
        "reasons": result.reasons,
    }
```

- [ ] **Step 2: Reiniciar servidor y probar**

```bash
kill $(ps aux | grep 'uvicorn app.api.main' | grep -v grep | awk '{print $2}') 2>/dev/null
sleep 2
cd ~/ibkr-bot && source .venv/bin/activate
nohup uvicorn app.api.main:app --host 127.0.0.1 --port 8088 --workers 1 > /tmp/uvicorn.log 2>&1 &
sleep 8
curl -s http://127.0.0.1:8088/account | python3 -m json.tool
curl -s http://127.0.0.1:8088/portfolio | python3 -m json.tool
curl -s http://127.0.0.1:8088/allowed-symbols | python3 -m json.tool
```

- [ ] **Step 3: Probar /orders/preview**

```bash
curl -s -X POST http://127.0.0.1:8088/orders/preview \
  -H "Content-Type: application/json" \
  -d '{"symbol":"AAPL","action":"BUY","quantity":1,"order_type":"MKT","stop_loss_pct":0.025,"take_profit_pct":0.06}' \
  | python3 -m json.tool
```

Esperado:
```json
{
  "approved": true,
  "symbol": "AAPL",
  "current_price": 286.07,
  "recommended_units": 2,
  "estimated_risk_usd": 14.30,
  ...
}
```

- [ ] **Step 4: Commit**

```bash
git add app/api/main.py
git commit -m "feat: add /account /portfolio /allowed-symbols /orders/preview endpoints"
```

---

## FASE 2: Base de Datos + Preprocesador

### Task 5: Capa de base de datos SQLite

**Files:**
- Create: `app/db/__init__.py`
- Create: `app/db/models.py`
- Create: `app/db/database.py`

- [ ] **Step 1: Crear app/db/models.py**

```python
# app/db/models.py
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class Signal:
    id: Optional[int]
    symbol: str
    strength: str
    rsi: float
    macd: float
    volume_ratio: float
    extra_indicators: str
    created_at: datetime
    processed: bool = False


@dataclass
class Trade:
    id: Optional[int]
    symbol: str
    action: str
    quantity: int
    entry_price: float
    stop_loss_price: float
    take_profit_price: float
    stop_loss_pct: float
    take_profit_pct: float
    signal_strength: str
    llm_justification: str
    status: str
    exit_price: Optional[float]
    exit_reason: Optional[str]
    pnl_usd: Optional[float]
    pnl_pct: Optional[float]
    opened_at: datetime
    closed_at: Optional[datetime]
    order_id: Optional[str]


@dataclass
class Pattern:
    id: Optional[int]
    symbol: str
    pattern_text: str
    win_count: int
    loss_count: int
    created_at: datetime
    updated_at: datetime


@dataclass
class SymbolConfig:
    symbol: str
    extra_indicators: str
    approved: bool
    proposed_by: str
    created_at: datetime


@dataclass
class Decision:
    id: Optional[int]
    signal_id: int
    symbol: str
    llm_model: str
    prompt_summary: str
    response: str
    action: str
    stop_loss_pct: float
    take_profit_pct: float
    created_at: datetime
```

- [ ] **Step 2: Crear app/db/database.py**

```python
# app/db/database.py
import sqlite3
import json
from datetime import datetime
from app.config.settings import DB_PATH, ALLOWED_SYMBOLS
from app.db.models import Signal, Trade, Pattern, Decision


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    conn = get_connection()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS signals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            strength TEXT NOT NULL,
            rsi REAL, macd REAL, volume_ratio REAL,
            extra_indicators TEXT DEFAULT '{}',
            created_at TEXT NOT NULL,
            processed INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL, action TEXT NOT NULL,
            quantity INTEGER NOT NULL, entry_price REAL NOT NULL,
            stop_loss_price REAL NOT NULL, take_profit_price REAL NOT NULL,
            stop_loss_pct REAL NOT NULL, take_profit_pct REAL NOT NULL,
            signal_strength TEXT NOT NULL, llm_justification TEXT,
            status TEXT NOT NULL DEFAULT 'OPEN',
            exit_price REAL, exit_reason TEXT,
            pnl_usd REAL, pnl_pct REAL,
            opened_at TEXT NOT NULL, closed_at TEXT, order_id TEXT
        );
        CREATE TABLE IF NOT EXISTS patterns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL, pattern_text TEXT NOT NULL,
            win_count INTEGER DEFAULT 0, loss_count INTEGER DEFAULT 0,
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS symbol_config (
            symbol TEXT PRIMARY KEY,
            extra_indicators TEXT DEFAULT '[]',
            approved INTEGER DEFAULT 1,
            proposed_by TEXT DEFAULT 'human',
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS decisions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            signal_id INTEGER, symbol TEXT NOT NULL,
            llm_model TEXT NOT NULL, prompt_summary TEXT, response TEXT,
            action TEXT NOT NULL, stop_loss_pct REAL, take_profit_pct REAL,
            created_at TEXT NOT NULL
        );
    """)
    now = datetime.utcnow().isoformat()
    for sym in ALLOWED_SYMBOLS:
        conn.execute(
            "INSERT OR IGNORE INTO symbol_config (symbol, approved, proposed_by, created_at) VALUES (?,1,'human',?)",
            (sym, now)
        )
    conn.commit()
    conn.close()


def insert_signal(signal: Signal) -> int:
    conn = get_connection()
    cur = conn.execute(
        "INSERT INTO signals (symbol,strength,rsi,macd,volume_ratio,extra_indicators,created_at) VALUES (?,?,?,?,?,?,?)",
        (signal.symbol, signal.strength, signal.rsi, signal.macd,
         signal.volume_ratio, signal.extra_indicators, signal.created_at.isoformat())
    )
    conn.commit()
    row_id = cur.lastrowid
    conn.close()
    return row_id


def get_pending_signals() -> list:
    conn = get_connection()
    rows = conn.execute("SELECT * FROM signals WHERE processed=0 ORDER BY created_at ASC").fetchall()
    conn.close()
    return [Signal(
        id=r["id"], symbol=r["symbol"], strength=r["strength"],
        rsi=r["rsi"], macd=r["macd"], volume_ratio=r["volume_ratio"],
        extra_indicators=r["extra_indicators"],
        created_at=datetime.fromisoformat(r["created_at"]),
        processed=bool(r["processed"]),
    ) for r in rows]


def mark_signal_processed(signal_id: int):
    conn = get_connection()
    conn.execute("UPDATE signals SET processed=1 WHERE id=?", (signal_id,))
    conn.commit()
    conn.close()


def insert_trade(trade: Trade) -> int:
    conn = get_connection()
    cur = conn.execute(
        """INSERT INTO trades
           (symbol,action,quantity,entry_price,stop_loss_price,take_profit_price,
            stop_loss_pct,take_profit_pct,signal_strength,llm_justification,status,opened_at,order_id)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (trade.symbol, trade.action, trade.quantity, trade.entry_price,
         trade.stop_loss_price, trade.take_profit_price, trade.stop_loss_pct,
         trade.take_profit_pct, trade.signal_strength, trade.llm_justification,
         trade.status, trade.opened_at.isoformat(), trade.order_id)
    )
    conn.commit()
    row_id = cur.lastrowid
    conn.close()
    return row_id


def get_open_trades() -> list:
    conn = get_connection()
    rows = conn.execute("SELECT * FROM trades WHERE status='OPEN'").fetchall()
    conn.close()
    return [Trade(
        id=r["id"], symbol=r["symbol"], action=r["action"],
        quantity=r["quantity"], entry_price=r["entry_price"],
        stop_loss_price=r["stop_loss_price"], take_profit_price=r["take_profit_price"],
        stop_loss_pct=r["stop_loss_pct"], take_profit_pct=r["take_profit_pct"],
        signal_strength=r["signal_strength"], llm_justification=r["llm_justification"],
        status=r["status"], exit_price=r["exit_price"], exit_reason=r["exit_reason"],
        pnl_usd=r["pnl_usd"], pnl_pct=r["pnl_pct"],
        opened_at=datetime.fromisoformat(r["opened_at"]),
        closed_at=datetime.fromisoformat(r["closed_at"]) if r["closed_at"] else None,
        order_id=r["order_id"],
    ) for r in rows]


def close_trade(trade_id: int, exit_price: float, exit_reason: str, pnl_usd: float, pnl_pct: float):
    conn = get_connection()
    conn.execute(
        "UPDATE trades SET status='CLOSED',exit_price=?,exit_reason=?,pnl_usd=?,pnl_pct=?,closed_at=? WHERE id=?",
        (exit_price, exit_reason, pnl_usd, pnl_pct, datetime.utcnow().isoformat(), trade_id)
    )
    conn.commit()
    conn.close()


def get_patterns_for_symbol(symbol: str) -> list:
    conn = get_connection()
    rows = conn.execute("SELECT * FROM patterns WHERE symbol=? ORDER BY win_count DESC", (symbol,)).fetchall()
    conn.close()
    return [Pattern(
        id=r["id"], symbol=r["symbol"], pattern_text=r["pattern_text"],
        win_count=r["win_count"], loss_count=r["loss_count"],
        created_at=datetime.fromisoformat(r["created_at"]),
        updated_at=datetime.fromisoformat(r["updated_at"]),
    ) for r in rows]


def insert_pattern(pattern: Pattern) -> int:
    conn = get_connection()
    cur = conn.execute(
        "INSERT INTO patterns (symbol,pattern_text,win_count,loss_count,created_at,updated_at) VALUES (?,?,?,?,?,?)",
        (pattern.symbol, pattern.pattern_text, pattern.win_count, pattern.loss_count,
         pattern.created_at.isoformat(), pattern.updated_at.isoformat())
    )
    conn.commit()
    row_id = cur.lastrowid
    conn.close()
    return row_id


def get_approved_symbols() -> list:
    conn = get_connection()
    rows = conn.execute("SELECT symbol FROM symbol_config WHERE approved=1").fetchall()
    conn.close()
    return [r["symbol"] for r in rows]


def insert_decision(decision: Decision) -> int:
    conn = get_connection()
    cur = conn.execute(
        """INSERT INTO decisions
           (signal_id,symbol,llm_model,prompt_summary,response,action,stop_loss_pct,take_profit_pct,created_at)
           VALUES (?,?,?,?,?,?,?,?,?)""",
        (decision.signal_id, decision.symbol, decision.llm_model,
         decision.prompt_summary, decision.response, decision.action,
         decision.stop_loss_pct, decision.take_profit_pct, decision.created_at.isoformat())
    )
    conn.commit()
    row_id = cur.lastrowid
    conn.close()
    return row_id
```

- [ ] **Step 3: Crear __init__.py e inicializar DB**

```bash
touch ~/ibkr-bot/app/db/__init__.py
cd ~/ibkr-bot && source .venv/bin/activate
python3 -c "from app.db.database import init_db; init_db(); print('DB OK')"
ls -la ibkr_trader.db
```
Esperado: `DB OK` y archivo creado.

- [ ] **Step 4: Commit**

```bash
git add app/db/
git commit -m "feat: add SQLite database layer with all tables"
```

---

### Task 6: Preprocesador de señales

**Files:**
- Create: `app/scanner/__init__.py`
- Create: `app/scanner/preprocessor.py`
- Create: `tests/test_preprocessor.py`

- [ ] **Step 1: Escribir tests del clasificador**

```python
# tests/test_preprocessor.py
from app.scanner.preprocessor import classify_signal


def test_strong_all_three():
    assert classify_signal(rsi=28.0, macd_crossover=True, volume_ratio=1.6) == "STRONG"


def test_strong_overbought():
    assert classify_signal(rsi=72.0, macd_crossover=True, volume_ratio=1.6) == "STRONG"


def test_medium_two_of_three():
    assert classify_signal(rsi=28.0, macd_crossover=True, volume_ratio=1.0) == "MEDIUM"


def test_medium_rsi_and_volume():
    assert classify_signal(rsi=72.0, macd_crossover=False, volume_ratio=1.6) == "MEDIUM"


def test_weak_one_condition():
    assert classify_signal(rsi=28.0, macd_crossover=False, volume_ratio=1.0) == "WEAK"


def test_weak_no_conditions():
    assert classify_signal(rsi=50.0, macd_crossover=False, volume_ratio=1.0) == "WEAK"
```

- [ ] **Step 2: Correr tests — verificar que fallan**

```bash
pytest tests/test_preprocessor.py -v
```
Esperado: `ModuleNotFoundError`

- [ ] **Step 3: Crear app/scanner/preprocessor.py**

```python
# app/scanner/preprocessor.py
import logging
from datetime import datetime
import pandas as pd
from app.config.settings import MARKET_TZ, MARKET_OPEN_HOUR, MARKET_OPEN_MINUTE, MARKET_CLOSE_HOUR, MARKET_CLOSE_MINUTE
from app.db.database import get_approved_symbols, insert_signal
from app.db.models import Signal

logger = logging.getLogger(__name__)


def classify_signal(rsi: float, macd_crossover: bool, volume_ratio: float) -> str:
    conditions = [rsi < 30 or rsi > 70, macd_crossover, volume_ratio > 1.5]
    count = sum(conditions)
    if count == 3:
        return "STRONG"
    if count == 2:
        return "MEDIUM"
    return "WEAK"


def _is_market_hours(now: datetime) -> bool:
    et = now.astimezone(MARKET_TZ)
    if et.weekday() >= 5:
        return False
    open_t = et.replace(hour=MARKET_OPEN_HOUR, minute=MARKET_OPEN_MINUTE, second=0)
    close_t = et.replace(hour=MARKET_CLOSE_HOUR, minute=MARKET_CLOSE_MINUTE, second=0)
    return open_t <= et <= close_t


def scan_symbol(symbol: str, ib_client) -> str | None:
    try:
        from ib_insync import Stock
        contract = Stock(symbol, "SMART", "USD")
        bars = ib_client.ib.reqHistoricalData(
            contract, endDateTime="", durationStr="30 D",
            barSizeSetting="1 day", whatToShow="TRADES",
            useRTH=True, formatDate=1,
        )
        if not bars or len(bars) < 15:
            logger.warning(f"Not enough bars for {symbol}")
            return None

        df = pd.DataFrame([{"close": b.close, "volume": b.volume} for b in bars])
        delta = df["close"].diff()
        gain = delta.clip(lower=0).rolling(14).mean()
        loss = (-delta.clip(upper=0)).rolling(14).mean()
        rs = gain / loss
        rsi = float((100 - 100 / (1 + rs)).iloc[-1])

        ema12 = df["close"].ewm(span=12).mean()
        ema26 = df["close"].ewm(span=26).mean()
        macd_line = ema12 - ema26
        signal_line = macd_line.ewm(span=9).mean()
        macd_crossover = (
            (macd_line.iloc[-2] < signal_line.iloc[-2] and macd_line.iloc[-1] > signal_line.iloc[-1]) or
            (macd_line.iloc[-2] > signal_line.iloc[-2] and macd_line.iloc[-1] < signal_line.iloc[-1])
        )

        avg_vol = df["volume"].rolling(20).mean().iloc[-1]
        volume_ratio = float(df["volume"].iloc[-1] / avg_vol) if avg_vol > 0 else 1.0

        strength = classify_signal(rsi=rsi, macd_crossover=macd_crossover, volume_ratio=volume_ratio)

        if strength in ("STRONG", "MEDIUM"):
            insert_signal(Signal(
                id=None, symbol=symbol, strength=strength,
                rsi=round(rsi, 2), macd=round(float(macd_line.iloc[-1]), 4),
                volume_ratio=round(volume_ratio, 2),
                extra_indicators="{}", created_at=datetime.now(tz=MARKET_TZ),
            ))
            logger.info(f"Signal {strength} for {symbol} RSI:{rsi:.1f} Vol:{volume_ratio:.2f}")
            return strength

        return None
    except Exception as e:
        logger.error(f"Error scanning {symbol}: {e}")
        return None


def run_scan(ib_client):
    now = datetime.now(tz=MARKET_TZ)
    if not _is_market_hours(now):
        logger.debug("Outside market hours — skipping scan")
        return
    symbols = get_approved_symbols()
    logger.info(f"Scanning {len(symbols)} symbols")
    for symbol in symbols:
        scan_symbol(symbol, ib_client)
```

- [ ] **Step 4: Crear __init__.py y correr tests**

```bash
touch ~/ibkr-bot/app/scanner/__init__.py
pytest tests/test_preprocessor.py -v
```
Esperado: todos PASS

- [ ] **Step 5: Commit**

```bash
git add app/scanner/ tests/test_preprocessor.py
git commit -m "feat: add signal preprocessor with RSI/MACD/volume classification"
```

---

## FASE 3: LLM Agent

### Task 7: Agente Kimi K2

**Files:**
- Create: `app/llm/__init__.py`
- Create: `app/llm/agent.py`

- [ ] **Step 1: Crear archivos**

```bash
mkdir -p ~/ibkr-bot/app/llm
touch ~/ibkr-bot/app/llm/__init__.py
```

- [ ] **Step 2: Crear app/llm/agent.py**

```python
# app/llm/agent.py
import json
import logging
from dataclasses import dataclass
from datetime import datetime
import httpx
from openai import OpenAI
from app.config.settings import LLM_BASE_URL, LLM_MODEL, LLM_API_KEY, MARKET_TZ
from app.db.database import get_patterns_for_symbol, insert_decision
from app.db.models import Decision

logger = logging.getLogger(__name__)
API_BASE = "http://127.0.0.1:8088"

TOOLS = [
    {"type": "function", "function": {
        "name": "get_price", "description": "Precio actual de un simbolo",
        "parameters": {"type": "object", "properties": {"symbol": {"type": "string"}}, "required": ["symbol"]},
    }},
    {"type": "function", "function": {
        "name": "get_portfolio", "description": "Posiciones abiertas",
        "parameters": {"type": "object", "properties": {}},
    }},
    {"type": "function", "function": {
        "name": "get_account", "description": "Balance y capital disponible",
        "parameters": {"type": "object", "properties": {}},
    }},
    {"type": "function", "function": {
        "name": "get_patterns", "description": "Patrones aprendidos para un simbolo",
        "parameters": {"type": "object", "properties": {"symbol": {"type": "string"}}, "required": ["symbol"]},
    }},
]


@dataclass
class LLMDecision:
    action: str            # BUY | SELL | IGNORE
    stop_loss_pct: float
    take_profit_pct: float
    justification: str
    confidence: str        # HIGH | MEDIUM | LOW


def _call_tool(name: str, args: dict) -> str:
    try:
        if name == "get_price":
            return httpx.get(f"{API_BASE}/price/{args['symbol']}", timeout=15).text
        elif name == "get_portfolio":
            return httpx.get(f"{API_BASE}/portfolio", timeout=15).text
        elif name == "get_account":
            return httpx.get(f"{API_BASE}/account", timeout=15).text
        elif name == "get_patterns":
            patterns = get_patterns_for_symbol(args["symbol"])
            return json.dumps([{"pattern": p.pattern_text, "wins": p.win_count, "losses": p.loss_count} for p in patterns])
    except Exception as e:
        return json.dumps({"error": str(e)})
    return json.dumps({"error": "unknown tool"})


def analyze_signal(symbol: str, strength: str, rsi: float, macd: float, volume_ratio: float, signal_id: int) -> LLMDecision:
    if not LLM_API_KEY:
        logger.warning("LLM_API_KEY not set — returning IGNORE")
        return LLMDecision("IGNORE", 0, 0, "LLM not configured", "LOW")

    llm = OpenAI(api_key=LLM_API_KEY, base_url=LLM_BASE_URL)
    system = """Eres un agente de swing trading. Analiza senales tecnicas y decide si entrar en una posicion.
REGLAS: take_profit debe ser al menos 2x el stop_loss. Si no hay evidencia suficiente, responde IGNORE.
FORMATO JSON estricto: {"action":"BUY"|"SELL"|"IGNORE","stop_loss_pct":0.025,"take_profit_pct":0.06,"justification":"...","confidence":"HIGH"|"MEDIUM"|"LOW"}"""

    user = f"Senal: {symbol} | Fuerza: {strength} | RSI: {rsi} | MACD: {macd} | Vol ratio: {volume_ratio}x\nUsa las herramientas para obtener precio, portafolio, capital y patrones aprendidos. Luego decide."

    messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]

    for _ in range(6):
        response = llm.chat.completions.create(
            model=LLM_MODEL, messages=messages, tools=TOOLS,
            tool_choice="auto", temperature=0.2,
        )
        msg = response.choices[0].message

        if msg.tool_calls:
            messages.append({"role": "assistant", "content": msg.content, "tool_calls": [
                {"id": tc.id, "type": "function", "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                for tc in msg.tool_calls
            ]})
            for tc in msg.tool_calls:
                messages.append({"role": "tool", "tool_call_id": tc.id,
                                  "content": _call_tool(tc.function.name, json.loads(tc.function.arguments))})
            continue

        try:
            content = msg.content.strip()
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
            data = json.loads(content)
            decision = LLMDecision(
                action=data.get("action", "IGNORE"),
                stop_loss_pct=float(data.get("stop_loss_pct", 0.02)),
                take_profit_pct=float(data.get("take_profit_pct", 0.04)),
                justification=data.get("justification", ""),
                confidence=data.get("confidence", "LOW"),
            )
            insert_decision(Decision(
                id=None, signal_id=signal_id, symbol=symbol, llm_model=LLM_MODEL,
                prompt_summary=user[:500], response=content, action=decision.action,
                stop_loss_pct=decision.stop_loss_pct, take_profit_pct=decision.take_profit_pct,
                created_at=datetime.now(tz=MARKET_TZ),
            ))
            logger.info(f"LLM: {symbol} -> {decision.action} SL:{decision.stop_loss_pct} TP:{decision.take_profit_pct}")
            return decision
        except (json.JSONDecodeError, KeyError) as e:
            logger.error(f"Failed to parse LLM response: {e}")
            break

    return LLMDecision("IGNORE", 0, 0, "Failed to parse LLM response", "LOW")
```

- [ ] **Step 3: Verificar importacion**

```bash
cd ~/ibkr-bot && source .venv/bin/activate
python3 -c "from app.llm.agent import analyze_signal; print('OK')"
```
Esperado: `OK`

- [ ] **Step 4: Commit**

```bash
git add app/llm/
git commit -m "feat: add Kimi K2 LLM agent with tool use"
```

---

## FASE 4: Position Manager + Orquestador

### Task 8: Daemon de posiciones

**Files:**
- Create: `app/positions/__init__.py`
- Create: `app/positions/manager.py`

- [ ] **Step 1: Crear archivos**

```bash
mkdir -p ~/ibkr-bot/app/positions
touch ~/ibkr-bot/app/positions/__init__.py
```

- [ ] **Step 2: Crear app/positions/manager.py**

```python
# app/positions/manager.py
import logging
import httpx
from app.config.settings import MIN_PROFIT_PCT_MEDIUM
from app.db.database import get_open_trades, close_trade

logger = logging.getLogger(__name__)
API_BASE = "http://127.0.0.1:8088"


def _get_current_price(symbol: str) -> float | None:
    try:
        return httpx.get(f"{API_BASE}/price/{symbol}", timeout=15).json().get("market_price")
    except Exception as e:
        logger.error(f"Could not fetch price for {symbol}: {e}")
        return None


def check_positions():
    trades = get_open_trades()
    if not trades:
        return

    for trade in trades:
        price = _get_current_price(trade.symbol)
        if price is None:
            continue

        pnl_pct = (price - trade.entry_price) / trade.entry_price
        if trade.action == "SELL":
            pnl_pct = -pnl_pct
        pnl_usd = pnl_pct * trade.entry_price * trade.quantity

        exit_reason = None

        if trade.action == "BUY":
            if price <= trade.stop_loss_price:
                exit_reason = "STOP_LOSS"
            elif price >= trade.take_profit_price:
                exit_reason = "TAKE_PROFIT"
            elif trade.signal_strength == "MEDIUM" and pnl_pct >= MIN_PROFIT_PCT_MEDIUM:
                exit_reason = "MIN_PROFIT_MEDIUM"
        elif trade.action == "SELL":
            if price >= trade.stop_loss_price:
                exit_reason = "STOP_LOSS"
            elif price <= trade.take_profit_price:
                exit_reason = "TAKE_PROFIT"

        if exit_reason:
            logger.info(f"Closing trade {trade.id} {trade.symbol} reason={exit_reason} pnl={pnl_pct:.2%} ${pnl_usd:.2f}")
            close_trade(
                trade_id=trade.id, exit_price=price, exit_reason=exit_reason,
                pnl_usd=round(pnl_usd, 2), pnl_pct=round(pnl_pct, 4),
            )
```

- [ ] **Step 3: Verificar importacion**

```bash
python3 -c "from app.positions.manager import check_positions; print('OK')"
```
Esperado: `OK`

- [ ] **Step 4: Commit**

```bash
git add app/positions/
git commit -m "feat: add position manager daemon"
```

---

### Task 9: Orquestador principal

**Files:**
- Create: `run.py`

- [ ] **Step 1: Crear run.py**

```python
# run.py
import logging
import uvicorn
from apscheduler.schedulers.background import BackgroundScheduler
from app.db.database import init_db
from app.ibkr.client import IBKRClient
from app.scanner.preprocessor import run_scan
from app.positions.manager import check_positions
from app.config.settings import SCAN_INTERVAL_MINUTES, POSITION_CHECK_MINUTES

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s - %(message)s")
logger = logging.getLogger(__name__)


def main():
    logger.info("Initializing database...")
    init_db()

    logger.info("Connecting to IB Gateway...")
    ib_client = IBKRClient()

    scheduler = BackgroundScheduler()
    scheduler.add_job(lambda: run_scan(ib_client), "interval", minutes=SCAN_INTERVAL_MINUTES, id="scanner")
    scheduler.add_job(lambda: check_positions(), "interval", minutes=POSITION_CHECK_MINUTES, id="position_manager")
    scheduler.start()
    logger.info(f"Scheduler started — scan every {SCAN_INTERVAL_MINUTES}min, positions every {POSITION_CHECK_MINUTES}min")

    logger.info("Starting FastAPI on 127.0.0.1:8088...")
    uvicorn.run("app.api.main:app", host="127.0.0.1", port=8088, workers=1)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Agregar endpoints de DB a main.py**

Agregar al final de `app/api/main.py`:

```python
from app.db.database import get_pending_signals, get_open_trades, get_patterns_for_symbol, init_db


@app.on_event("startup")
def startup():
    init_db()


@app.get("/signals")
def get_signals():
    return [{"id": s.id, "symbol": s.symbol, "strength": s.strength,
             "rsi": s.rsi, "macd": s.macd, "volume_ratio": s.volume_ratio,
             "created_at": s.created_at.isoformat()} for s in get_pending_signals()]


@app.get("/trades")
def get_trades():
    return [{"id": t.id, "symbol": t.symbol, "action": t.action,
             "quantity": t.quantity, "entry_price": t.entry_price,
             "stop_loss_price": t.stop_loss_price, "take_profit_price": t.take_profit_price,
             "signal_strength": t.signal_strength, "status": t.status,
             "opened_at": t.opened_at.isoformat()} for t in get_open_trades()]


@app.get("/patterns/{symbol}")
def get_patterns(symbol: str):
    return [{"id": p.id, "pattern": p.pattern_text, "wins": p.win_count,
             "losses": p.loss_count} for p in get_patterns_for_symbol(symbol.upper())]
```

- [ ] **Step 3: Probar arranque completo**

```bash
kill $(ps aux | grep 'uvicorn\|run.py' | grep -v grep | awk '{print $2}') 2>/dev/null
sleep 2
cd ~/ibkr-bot && source .venv/bin/activate
python3 run.py &
sleep 8
curl -s http://127.0.0.1:8088/health
curl -s http://127.0.0.1:8088/signals
curl -s http://127.0.0.1:8088/trades
```
Esperado: health OK, signals y trades como arrays JSON.

- [ ] **Step 4: Correr todos los tests**

```bash
pytest tests/ -v
```
Esperado: todos PASS

- [ ] **Step 5: Commit final**

```bash
git add run.py app/api/main.py
git commit -m "feat: add main orchestrator with APScheduler + DB endpoints"
```

---

## Self-Review

**Cobertura del spec:**
- Phase 1 endpoints: /health /price /account /portfolio /allowed-symbols /symbols/propose /orders/preview — Task 4
- Motor de riesgo determinístico — Task 3
- DB SQLite con todas las tablas — Task 5
- Preprocesador RSI+MACD+volumen sin LLM — Task 6
- LLM Agent Kimi K2 con tool use — Task 7
- Position Manager stop-loss/take-profit — Task 8
- Orquestador APScheduler — Task 9
- /signals /trades /patterns — Task 9

**Pendiente (fases futuras):**
- /orders/place ejecucion real (Fase 5)
- Telegram bot (Fase 5)
- Post-mortem LLM + patrones (Fase 6)
- systemd services (Fase 7)

**Consistencia de tipos verificada:**
- IBKRClient._run_sync() en todos los metodos publicos
- validate_order() devuelve ValidationResult
- classify_signal() devuelve str literal
- analyze_signal() devuelve LLMDecision
- DB functions usan get_connection() por llamada (thread-safe SQLite)
