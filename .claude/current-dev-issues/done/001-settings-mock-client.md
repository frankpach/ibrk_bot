# Issue 001: Settings centralization + MockIBClient

**Module**: dev-plan
**Type**: AFK
**Effort**: S
**Blocked by**: None
**Requires review**: false

---

## WHY — The Human Problem

**User pain**: El código tiene `API_BASE = "http://127.0.0.1:8088"` hardcodeado en 7 archivos y `OPENCODE_BIN` hardcodeado en 2. Desarrollar localmente en Windows es imposible sin cambiar código — y hay que conectar IB Gateway en la Pi para cualquier test.

**Business impact**: Sin MockIBClient y sin configuración via env, ningún nuevo módulo puede desarrollarse ni testearse localmente. Bloquea todos los issues P0 siguientes.

**Success signal**: `pytest tests/` pasa completamente en Windows con `IB_MOCK=true` en `.env.local` sin modificar ningún archivo de código.

---

## WHO

| Persona | Role | Device | Environment | Goal | Constraint |
|---|---|---|---|---|---|
| Frank | Developer | PC Windows | Local dev | Correr tests sin Pi conectada | No tiene IB Gateway en Windows |
| Sistema | Bot Pi | Raspberry Pi | Production | Misma config que dev, distinto .env | Sin cambios de código entre dev y prod |

**Primary user**: Frank como developer.

---

## WHAT — Constraints

- [ ] `IB_HOST`, `IB_PORT`, `API_BASE`, `OPENCODE_BIN`, `OPENCODE_MODEL`, `IB_MOCK`, `IB_CLIENT_ID_DATA` deben venir de `os.getenv()` en `settings.py`
- [ ] MockIBClient implementa exactamente la misma interfaz pública que IBKRClient
- [ ] `IB_MOCK=true` NUNCA conecta a IB real — ningún socket abierto
- [ ] IBKRClient NO se modifica — MockIBClient es un módulo nuevo
- [ ] Los 95 tests existentes siguen pasando sin cambios

**Module-specific rules**:
- [ ] `from app.config.settings import API_BASE` debe funcionar en todos los módulos que hoy tienen `API_BASE = "..."` hardcodeado
- [ ] MockIBClient retorna datos determinísticos (semilla fija) para reproducibilidad

---

## HOW — Implementation Approach

**settings.py** — agregar/modificar:
```python
IB_HOST = os.getenv("IB_HOST", "127.0.0.1")
IB_PORT = int(os.getenv("IB_PORT", "4002"))
OPENCODE_BIN = os.getenv("OPENCODE_BIN", "/home/frankpach/.opencode/bin/opencode")
OPENCODE_MODEL = os.getenv("OPENCODE_MODEL", "opencode-go/qwen3.5-plus")
API_BASE = os.getenv("API_BASE", "http://127.0.0.1:8088")
IB_MOCK = os.getenv("IB_MOCK", "false").lower() == "true"
IB_CLIENT_ID_DATA = int(os.getenv("IB_CLIENT_ID_DATA", "12"))
```

**7 archivos a actualizar** (eliminar `API_BASE = "http://..."` hardcodeado, importar desde settings):
- `app/alerts/manager.py`
- `app/notifications/telegram_bot.py`
- `app/positions/manager.py`
- `app/llm/loop.py`
- `app/llm/agent.py`
- `app/mcp/server.py`
- `app/backtest/engine.py` (si aplica)

**2 archivos a actualizar** (OPENCODE_BIN):
- `app/llm/agent.py`
- `app/notifications/telegram_bot.py`

**app/analysis/mock_client.py** (nuevo):
- Misma interfaz que IBKRClient: `get_stock_price()`, `get_account()`, `get_portfolio()`, `place_order()`, `disconnect()`
- Atributo `self.ib` con `isConnected()` → True
- `ib.reqHistoricalData()` retorna 180 barras sintéticas determinísticas (seed=42 via numpy)
- `ib.reqScannerData()` retorna lista fija de tickers: `["NFLX", "SHOP", "PLTR", "COIN", "RBLX"]`
- `ib.reqHistoricalNews()` retorna 2 items fijos
- `ib.reqFundamentalData()` retorna XML mínimo con earnings date en 15 días
- `place_order()` retorna `{"order_id": "mock_001", "status": "Submitted"}`

**app/analysis/__init__.py** (nuevo, vacío)

**.env.local** (nuevo en raíz del proyecto para Windows dev):
```
IB_HOST=100.92.245.100
IB_PORT=4002
IB_MOCK=true
API_BASE=http://127.0.0.1:8088
OPENCODE_BIN=/path/to/opencode/on/windows
DB_PATH=ibkr_trader_dev.db
```

---

## Code Search

- [ ] Verificado: `grep -rn "API_BASE\|127.0.0.1:8088" app/` — 7 archivos confirmados
- [ ] Verificado: `grep -rn "OPENCODE_BIN\|frankpach" app/` — 2 archivos confirmados
- [ ] Verificado: IBKRClient interfaz pública en `app/ibkr/client.py` — métodos a replicar en mock

**Reuse decision**:
- Reuse as-is: IBKRClient (solo referencia para interfaz)
- Extend: settings.py (agregar vars)
- Build new: MockIBClient, app/analysis/__init__.py

---

## Reference Documents

| Document | Path | What to Extract |
|---|---|---|
| PRD | docs/dev/artifacts/dev-plan/08-prd.md | REQ-01, REQ-02 con ACs |
| Architecture map | docs/dev/artifacts/dev-plan/03-architecture-map.md | Anti-pattern hardcoded infrastructure |
| Constraints | .claude/current-dev-issues/.state/constraints.md | IB_MOCK rules, client_id rules |

---

## Acceptance Criteria

- [ ] AC-01.1: Con `.env.local` `IB_HOST=100.92.245.100`, el sistema usa esa IP sin cambiar código
- [ ] AC-01.2: Con `IB_MOCK=true`, ningún socket se abre hacia IB Gateway
- [ ] AC-01.3: `from app.config.settings import API_BASE` importa correctamente en todos los módulos modificados
- [ ] AC-02.1: `pytest tests/` con `IB_MOCK=true` pasa completamente sin Pi conectada
- [ ] AC-02.2: `MockIBClient.get_stock_price("AAPL")` retorna `{"market_price": 287.50, ...}` determinístico
- [ ] AC-02.3: `MockIBClient` no abre sockets de red
- [ ] 95 tests existentes siguen pasando sin modificaciones a los tests

## Definition of Done

- [ ] Todos los ACs verificados
- [ ] `pytest tests/ -v` → 95+ PASS en Windows con IB_MOCK=true
- [ ] Ningún archivo de código tiene `API_BASE` o `OPENCODE_BIN` hardcodeados
- [ ] `app/analysis/__init__.py` y `mock_client.py` creados
- [ ] `.env.local` documentado en README o `.env.example`
- [ ] Issue movido a `done/`
