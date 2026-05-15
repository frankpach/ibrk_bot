# Architecture: IBKR AI Trader — Hexagonal Architecture

## Layer Diagram

```
┌────────────────────────────────────────────────────────┐
│  INTERFACES                                            │
│  app/interfaces/api/routes/   app/notifications/       │
│  app/api/                     telegram_bot.py          │
│  app/bootstrap/scheduler_setup.py (APScheduler)        │
├────────────────────────────────────────────────────────┤
│  APPLICATION                                           │
│  app/application/use_cases/   app/application/         │
│  app/application/services/    event_bus.py             │
│  app/application/ports/       (IBrokerPort, ILLMPort,  │
│                               INotificationPort)       │
├────────────────────────────────────────────────────────┤
│  DOMAIN                                                │
│  app/domain/trading/events.py                          │
│  app/domain/trading/value_objects.py                   │
├────────────────────────────────────────────────────────┤
│  INFRASTRUCTURE                                        │
│  app/infrastructure/broker/   (IBKRBrokerAdapter)      │
│  app/infrastructure/db/       (SQLAlchemy + Alembic)   │
│  app/infrastructure/llm/      (OpenCodeAdapter)        │
│  app/infrastructure/notifications/ (TelegramAdapter)   │
│  app/infrastructure/system/   (AuditLogHandler,        │
│                               SecretManager)           │
│  app/ibkr/                    (IBKRClient — wrapped)   │
└────────────────────────────────────────────────────────┘
```

## DI Container (`app/container.py`)

Single source of truth for all wired dependencies. Accessed via `get_container()` (cached singleton) or `test_container()` (fresh, all mocks, in-memory SQLite).

```python
class Container:
    broker: IBrokerPort           # IBKRBrokerAdapter or MockBrokerAdapter
    notifier: INotificationPort   # TelegramNotificationAdapter or Mock
    event_bus: EventBus
    risk_service: RiskService
    position_service: PositionService
    secret_manager: SecretManager
    engine: Engine                # SQLAlchemy engine (SQLite or PostgreSQL)
    alert_manager: AlertManager
    order_deduplicator: OrderDeduplicator
    place_order_use_case: PlaceOrderUseCase
    close_position_use_case: ClosePositionUseCase
```

**Critical rule**: Never call `get_container()` at module import time. Always call it inside a function body to avoid circular imports.

## Event Bus (`app/application/event_bus.py`)

In-process synchronous pub/sub. Handlers registered in `Container._register_event_handlers()`.

```python
event_bus.subscribe(TradingModeSwitched, audit_handler.handle)
event_bus.subscribe(OrderPlaced, audit_handler.handle)
event_bus.publish(TradingModeSwitched(old_mode="paper", new_mode="live", ...))
```

**Current event catalog** (all in `app/domain/trading/events.py`):

| Event | Publisher | Handlers |
|-------|-----------|---------|
| `TradingModeSwitched` | `ChangeTradingModeUseCase` | AuditLog, Telegram |
| `SystemPaused` | `PauseSystemUseCase` | AuditLog, Telegram |
| `SystemResumed` | `ResumeSystemUseCase` | AuditLog, Telegram |
| `ControlSettingChanged` | `UpdateControlSettingUseCase` | AuditLog |
| `OrderPlaced` | `PlaceOrderUseCase` | AuditLog |
| `PositionClosed` | `ClosePositionUseCase` | AuditLog, Telegram |
| `CircuitBreakerTriggered` | `RiskService` | AuditLog, Telegram |

**Known limitation**: `EventBus` has no `unsubscribe()` method. Do NOT subscribe long-lived handlers inside per-request or per-pipeline scopes — only register handlers once at container init time.

## Database (`app/infrastructure/db/`)

| File | Purpose |
|------|---------|
| `engine.py` | `get_engine(url)` — SQLite or PostgreSQL, WAL mode |
| `base.py` | `DeclarativeBase` for all models |
| `session.py` | `get_session()` context manager |
| `compat.py` | Legacy wrapper for 75 functions — not to be extended |
| `models/` | 23 SQLAlchemy models |
| `migrations/` | Alembic versioned migrations |

**Dual-backend support**: Same code runs on both:
- `sqlite:///./ibkr_trader.db` (default, Pi production)
- `postgresql://user:pass@host/ibkr` (future)

Run migrations: `alembic upgrade head`

## SQLAlchemy Models

| Model | Table | Key Purpose |
|-------|-------|-------------|
| `TradeModel` | `trades` | Full position lifecycle |
| `SignalModel` | `signals` | Pending LLM signals |
| `SymbolConfigModel` | `symbol_config` | Approved trading universe |
| `SymbolParameterModel` | `symbol_parameters` | Adaptive per-symbol params |
| `ControlSettingModel` | `control_settings` | Persisted system config |
| `AuditLogModel` | `audit_log` | Immutable event history |
| `BackgroundJobModel` | `background_jobs` | Async job status |
| `PatternModel` | `patterns` | LLM historical memory |
| `FeatureSnapshotModel` | `feature_snapshots` | ML retraining input |
| `AccountSnapshotModel` | `account_snapshots` | EOD account P&L |

## Ports (Interfaces)

| Port | File | Implementations |
|------|------|----------------|
| `IBrokerPort` | `app/application/ports/broker_port.py` | `IBKRBrokerAdapter`, `MockBrokerAdapter` |
| `INotificationPort` | `app/application/ports/notification_port.py` | `TelegramNotificationAdapter`, `MockNotificationAdapter` |
| `ILLMPort` | `app/application/ports/llm_port.py` | `OpenCodeAdapter`, `MockLLMAdapter` *(not yet wired in Container)* |

## Use Cases

| Use Case | File | What It Does |
|----------|------|-------------|
| `PlaceOrderUseCase` | `use_cases/place_order.py` | Symbol lock, risk validation, broker integration |
| `ClosePositionUseCase` | `use_cases/close_position.py` | Idempotent position close |
| `ChangeTradingModeUseCase` | `use_cases/change_mode.py` | Validates open positions, persists mode, reconnects |
| `PauseSystemUseCase` | `use_cases/pause_system.py` | Persists pause state, publishes event |
| `UpdateControlSettingUseCase` | `use_cases/update_control_setting.py` | Validates + persists + publishes ControlSettingChanged |
| `ControlQueries` | `use_cases/control_queries.py` | Read-only control settings access |

## LLM Integration

Single `OpenCodeAdapter` in `app/infrastructure/llm/opencode_adapter.py` — the three legacy duplicates of `_call_opencode()` are deleted. Hardened subprocess: `SAFE_SYMBOL_RE` validation, `env={}`, `X_OK` flag check.

## Background Jobs

`ThreadPoolExecutor(max_workers=3)` in `app/application/services/job_runner.py`. Long-running operations (LLM analysis, backtest, opportunity scan) are submitted as jobs. API: `POST /jobs/{type}` → `{job_id}`, `GET /jobs/{id}` → `{status, result}`.

## Security

- Two-tier auth: `X-Control-Key` (standard ops) + `X-Admin-Key` (high-impact: mode change, API keys, ports)
- API keys encrypted with Fernet (`app/infrastructure/system/secret_manager.py`), never returned plain in API responses
- Security headers: CORS restrictivo, `X-Frame-Options`, `X-Content-Type-Options`, `Referrer-Policy`
- systemd unit hardened: `NoNewPrivileges`, `PrivateTmp`, `MemoryDenyWriteExecute`
- `.env.secret` in `.gitignore`
