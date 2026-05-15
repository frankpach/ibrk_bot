# API Reference: IBKR AI Trader

Base URL (Pi): `http://aiutox-pi:8088`

## Authentication

| Header | Used For |
|--------|---------|
| `X-Control-Key` | Standard operations (most endpoints) |
| `X-Admin-Key` | High-impact: mode change, API keys, IB ports, symbol approval |

## Trading Routes (`app/interfaces/api/routes/trading_routes.py`)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/orders/place` | Control | Place order via `PlaceOrderUseCase` |
| `POST` | `/orders/close/{symbol}` | Control | Close position via `ClosePositionUseCase` |
| `GET` | `/trades` | Control | List open trades |
| `GET` | `/trades/{id}` | Control | Trade detail |

## System Routes (`app/interfaces/api/routes/system_routes.py`)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/system/state` | Control | Current mode + pause state |
| `POST` | `/system/mode` | **Admin** | Switch paper/live via `ChangeTradingModeUseCase` |
| `POST` | `/system/pause` | Control | Pause via `PauseSystemUseCase` |
| `POST` | `/system/resume` | Control | Resume via `PauseSystemUseCase` |
| `GET` | `/health` | None | Liveness check |

## Control Plane Routes (`app/api/control_plane.py`)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/control/settings` | Control | All persisted settings |
| `PUT` | `/control/settings/{key}` | Admin (if sensitive) | Update setting |
| `GET` | `/control/audit-log` | Control | Recent audit entries |
| `GET` | `/control/symbols` | Control | Approved symbol universe |
| `POST` | `/control/symbols/approve` | **Admin** | Approve new symbol |

## Market Routes (`app/interfaces/api/routes/market_routes.py`)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/price/{symbol}` | Control | Current price via broker |
| `GET` | `/signals` | Control | Pending signals |
| `GET` | `/portfolio` | Control | Current positions from IBKR |

## Analysis Routes (`app/interfaces/api/routes/analysis_routes.py` + jobs)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/analyze/{symbol}` | Control | Trigger on-demand analysis (async job) |
| `GET` | `/candidate-analysis/{symbol}` | Control | Latest analysis result |
| `POST` | `/backtest/{symbol}` | Control | Trigger backtest (async job) |

## Jobs Routes (`app/interfaces/api/routes/jobs_routes.py`)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/jobs/{type}` | Control | Submit background job |
| `GET` | `/jobs/{id}` | Control | Poll job status |

## Reports Routes (`app/interfaces/api/routes/reports_routes.py`)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/reports` | Control | List generated reports |
| `GET` | `/reports/{id}` | Control | Report content |

## Dashboard

| Path | Description |
|------|-------------|
| `/` | Main trading dashboard (React SPA) |
| `/control` | Control plane (React SPA) |
