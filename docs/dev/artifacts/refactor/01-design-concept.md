# Design Concept: Refactor Arquitectónico — IBKR AI Trader

**Status**: ✓ Complete  
**Date**: 2026-05-14  
**Module**: refactor  

---

## Problem Statement

> El sistema de trading IBKR AI Trader funciona en producción pero tiene una deuda arquitectónica que lo hace frágil, difícil de mantener y de testear. Los módulos internos se comunican vía HTTP entre ellos dentro del mismo proceso, el estado operativo crítico (modo paper/live, pausa) vive en memoria y se pierde en cada restart, la base de datos es un monolito de 1,277 líneas que importan 35 módulos simultáneamente, y no hay forma de cambiar parámetros operativos sin editar `.env` y reiniciar el servidor. El crecimiento actual lleva a bugs silenciosos, race conditions latentes y riesgo operativo real en producción.

---

## Solution

El refactor transforma el sistema en una arquitectura de capas desacopladas (Ports/Adapters/Use Cases) con las siguientes mejoras fundamentales:

1. **Eliminar HTTP interno**: `llm/loop.py` y `positions/manager.py` dejan de llamar a FastAPI vía `httpx`; usan servicios Python directos.
2. **Persistir estado operativo**: modo paper/live, pausa del sistema, todos los parámetros de riesgo persisten en DB — no en memoria.
3. **Descomponer el monolito de DB**: `database.py` se divide en repositorios SQLAlchemy por entidad, con migraciones versionadas (Alembic).
4. **Control plane `/control`**: UI centralizada donde configurar todo: API keys cifradas, puertos IB (4002/4001), DB URL, parámetros de riesgo, universo de símbolos — arranca desde `.env` pero se puede modificar en caliente.
5. **Event bus interno**: los módulos emiten eventos; Telegram, auditoría y postmortem son handlers registrados, no llamadas directas dispersas.
6. **Background jobs con estado**: análisis LLM, backtest, learning cycle salen del request path; el dashboard hace polling a un job status.
7. **Soporte dual SQLite/PostgreSQL**: repositorios SQLAlchemy compatibles con ambos backends; plan de migración de 4 fases.
8. **Hardening de seguridad**: dos niveles de auth (Control Key / Admin Key), audit log completo, subprocess hardening, secretos cifrados.

---

## Key Personas

### Persona 1: Frank — Trader (rol operativo)
- **Quién**: El dueño/operador del sistema. Supervisa posiciones abiertas, aprueba órdenes en modo live, cambia parámetros de riesgo, pausa el sistema ante eventos de mercado.
- **Device**: Desktop/laptop (dashboard web) + móvil (Telegram bot)
- **Entorno**: Casa/oficina. Monitoreo activo durante horario de mercado (9:30–16:30 ET). Consultas puntuales fuera de horario.
- **Goal**: Operar con confianza sabiendo que el sistema no va a perder estado en un restart, que puede ajustar parámetros sin tocar código, y que hay trazabilidad completa de cada decisión.
- **Maior constraint**: No puede estar mirando el sistema constantemente — necesita que el sistema opere autónomamente con los parámetros que él configura.

### Persona 2: Frank — Developer (rol de mantenimiento)
- **Quién**: El mismo usuario, pero en modo desarrollo: añade features, refactoriza código, debuggea el scheduler, corre migraciones, revisa logs, escribe tests.
- **Device**: Desktop/laptop con IDE, terminal, acceso SSH a la Raspberry Pi vía Tailscale.
- **Entorno**: Local (testing en modo paper) + Pi (producción en modo live/paper real).
- **Goal**: Poder hacer cambios con confianza — tests que validan que el trading no se rompe, módulos pequeños y focalizados que se puedan revisar en un PR sin entender todo el sistema, migraciones que se aplican sin downtime.
- **Mayor constraint**: El sistema no tiene equipo — es solo él. Cada bug en producción lo impacta directamente. El costo de un refactor que rompe producción es inaceptable.

---

## Constraints

### Timeline
- **Fecha límite**: Sin fecha fija
- **Ritmo**: Incremental, fase por fase, sin presión
- **Blocking issues**: El sistema está en producción activo — ninguna fase puede dejarlo inoperativo

### Technical
- **ORM**: SQLAlchemy (para ambos backends — SQLite y PostgreSQL)
- **Migraciones**: Alembic (integrado con SQLAlchemy)
- **Framework API**: FastAPI (se mantiene)
- **Scheduler**: APScheduler (se mantiene)
- **Broker**: ib_insync (se mantiene, encapsulado en adapter)
- **LLM**: OpenCode subprocess (se consolida en 1 adapter)
- **Notificaciones**: python-telegram-bot (se mantiene)
- **Backend DB hoy**: SQLite con WAL mode
- **Backend DB objetivo**: PostgreSQL
- **Entorno testing**: Local (modo paper)
- **Entorno producción**: Raspberry Pi + IB Gateway, acceso vía Tailscale
- **Proceso**: Único hoy; diseñar sin bloquear separación en workers futuros

### Business
- **Sistema en producción activa**: rollback debe ser posible en cada fase
- **Sin equipo**: el desarrollador/operador es la misma persona
- **Acceso privado por Tailscale**: no hay exposición pública, pero no se asume confianza total interna
- **Success metrics**:
  - Estado operativo sobrevive restart (modo, pausa, parámetros)
  - Tests unitarios posibles sin IB Gateway ni Telegram
  - Cualquier parámetro operativo configurable desde `/control` sin tocar código
  - Audit log de todos los cambios de configuración
  - Dashboard `/control` sin datos hardcodeados en `.env`

---

## Scope: In vs Out

### In Scope

**Fase 0 — Quick wins:**
- Unificar `_call_opencode()` en 1 adapter (eliminar 3 duplicaciones)
- `@contextmanager transaction(conn)` para operaciones atómicas
- Persistir `is_paused` + `mode` en DB desde el primer día
- Logging estructurado con `symbol` + `trade_id`

**Fase 1 — Eliminar HTTP interno:**
- `loop.py` → llama `PlaceOrderUseCase` directamente
- `positions/manager.py` → llama `IBrokerPort.get_price()` directamente
- `alerts/manager.py` → llama `IBrokerPort.get_price()` directamente
- Crear `IBrokerPort`, `IBKRBrokerAdapter`, `MockBrokerAdapter`

**Fase 2 — Extraer servicios:**
- Dividir `api/main.py` en 6 route files
- Extraer use cases: `PlaceOrderUseCase`, `ClosePositionUseCase`, `ChangeTradingModeUseCase`
- Crear `RiskService`, `PositionService`
- Crear `container.py` (DI)
- Slim down `run.py` a ~50 LOC

**Fase 3 — Persistir system state:**
- Tabla `control_settings` (key-value cifrado para secrets)
- Tabla `audit_log` expandida
- `PersistedSystemState` reemplaza `SystemController` con globals mutables
- `ChangeTradingModeUseCase` persiste modo + puerto IB (4002/4001)

**Fase 4 — Control plane `/control`:**
- UI accesible desde header del dashboard
- Secciones: modo operativo, parámetros de riesgo, circuit breaker, universo de símbolos, parámetros adaptativos, notificaciones, human approval, feature flags, conectividad IB, fuente de datos, jobs/scheduler
- Gestión de API keys cifradas (no plain text en DB)
- Configuración de puertos IB (4002 paper / 4001 live)
- Configuración de DB URL (arranca desde `.env`, editable en caliente)
- Dos niveles de auth: Control Key + Admin Key
- Audit log de todos los cambios desde `/control`
- Hot-reload para parámetros operativos; banner de advertencia para settings que requieren restart

**Fase 5 — Dashboard solo lectura:**
- `DashboardDataQuery` SQLAlchemy (1-2 queries agregadas)
- Read models separados de repositorios operativos
- Background jobs para LLM analysis, backtest, opportunity scan
- API de polling: `POST /jobs/{type}` → `{ job_id }`, `GET /jobs/{id}` → `{ status, result }`

**Fase 6 — Doble soporte SQLite/PostgreSQL:**
- Repositorios SQLAlchemy con modelos declarativos
- Migraciones Alembic versionadas
- Tests parametrizados por backend (`@pytest.fixture(params=["sqlite", "postgres"])`)
- `DatabaseConfig` con URL paramétrica

**Fase 7 — Migrar a PostgreSQL:**
- Script de migración de datos SQLite → PostgreSQL
- Dry-run con checksums
- Ventana de mantenimiento con rollback claro

**Fase 8 — Hardening final:**
- Eliminar SQLite code paths
- systemd hardening (`NoNewPrivileges`, `PrivateTmp`, `ProtectSystem`)
- Secretos en `systemd` credentials o archivo cifrado (no en código)
- Security headers FastAPI (CORS restrictivo, CSP)
- Subprocess hardening: validar path OpenCode, sanitizar símbolo antes de incluir en prompt
- TLS verificado en Tailscale

### Out of Scope
- Exposición pública a internet (no es objetivo)
- Mobile app nativa (no aplica)
- Multi-usuario / multi-tenant (sistema personal)
- Notificaciones SMS (solo Telegram)
- Workers separados en procesos distintos (Fase 9, opcional futuro)
- Integración con brokers distintos a IBKR
- UI de backtesting completo (el backtest endpoint existe; mejorar UI es futuro)
- IA/ML nuevas features (el refactor no añade nuevas capabilities de trading)

**Por qué fuera de scope:** El objetivo es estabilizar y desacoplar, no añadir features. La Fase 9 (workers separados) queda como roadmap futuro porque el sistema en proceso único es completamente funcional y la complejidad operativa de múltiples procesos no se justifica hoy.

---

## Open Questions

- [ ] **Cifrado de API keys en `control_settings`**: ¿usar Fernet (cryptography lib) con clave derivada del `API_CONTROL_KEY` existente, o un mecanismo diferente?
  - *Implicación*: Afecta el diseño del `SettingValidator` y cómo se muestran en UI (campo tipo password)
- [ ] **Alembic en SQLite**: Alembic tiene limitaciones para SQLite (no soporta todas las operaciones de `ALTER TABLE`). ¿Aceptamos un script de migración manual para SQLite + Alembic completo solo para PostgreSQL?
  - *Implicación*: Determina si SQLite sigue siendo soportado en producción post-Fase 6
- [ ] **Puerto IB en cambio de modo**: El cambio paper(4002)→live(4001) requiere reconectar `IBKRClient`. ¿La reconexión debe ser automática o requiere restart del servicio?
  - *Implicación*: Complejidad del `ChangeTradingModeUseCase`
- [ ] **Granularidad del Admin Key**: ¿El Admin Key se usa solo para cambio a modo live + approve símbolos, o también para cualquier cambio de parámetros de riesgo?
  - *Implicación*: Diseño del modelo de permisos en `/control`

---

## Assumptions

- [x] **Sistema single-user**: Solo Frank opera y mantiene el sistema. No hay otros usuarios.
- [x] **Sin fecha límite**: El refactor avanza a ritmo libre, fase por fase.
- [x] **Local = testing, Pi = producción**: Los cambios se validan localmente antes de deployar en la Pi.
- [x] **SQLAlchemy como ORM**: Se usa SQLAlchemy para todos los repositorios (no SQL plano).
- [x] **Alembic para migraciones**: Migraciones versionadas, reemplaza los `ALTER TABLE` en try/except actuales.
- [ ] **Fernet para cifrado de secrets**: Se asume que `cryptography.Fernet` es aceptable para cifrar API keys en `control_settings`. *(pendiente confirmación)*
- [ ] **Reconexión IB en cambio de modo**: Se asume que el cambio de puerto requiere reconexión automática del client IB, no restart del servicio. *(pendiente confirmación)*
- [ ] **SQLite descartado en producción final**: Se asume que tras Fase 7, producción corre solo PostgreSQL. *(pendiente confirmación)*

---

## Recomendaciones Adicionales (todas las del arquitecto)

### SQLAlchemy — Diseño Específico

**Usar modelos declarativos con `DeclarativeBase`:**
```python
# infrastructure/db/base.py
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import create_engine, String, Float, Boolean, DateTime

class Base(DeclarativeBase):
    pass

# infrastructure/db/models/trade.py
class TradeModel(Base):
    __tablename__ = "trades"
    id: Mapped[int] = mapped_column(primary_key=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="PENDING")
    entry_price: Mapped[float] = mapped_column(Float, nullable=True)
    # ... resto de columnas
```

**Session management con context manager:**
```python
# infrastructure/db/session.py
from contextlib import contextmanager
from sqlalchemy.orm import Session

@contextmanager
def get_session(engine) -> Session:
    with Session(engine) as session:
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
```

**Alembic setup:**
```
alembic init infrastructure/db/migrations
# env.py apunta a Base.metadata
# alembic.ini usa DATABASE_URL
```

### Control Plane — Cifrado de Secrets

```python
# infrastructure/system/secret_manager.py
from cryptography.fernet import Fernet
import os

class SecretManager:
    def __init__(self):
        key = os.environ.get("SECRET_ENCRYPTION_KEY")
        if not key:
            raise RuntimeError("SECRET_ENCRYPTION_KEY not set")
        self._fernet = Fernet(key.encode())
    
    def encrypt(self, value: str) -> str:
        return self._fernet.encrypt(value.encode()).decode()
    
    def decrypt(self, encrypted: str) -> str:
        return self._fernet.decrypt(encrypted.encode()).decode()
```

Secrets marcados con `is_secret=True` en `control_settings` nunca se devuelven en plain text vía API.

### Estrategia de Migración SQLite → Alembic

Dado que SQLite tiene limitaciones con `ALTER TABLE`, la estrategia es:

1. **Hoy (SQLite)**: Alembic en modo "offline" genera SQL que se aplica manualmente para operaciones complejas; para operaciones simples (añadir columna NOT NULL con default) funciona directo.
2. **Tras Fase 6**: Alembic completo contra PostgreSQL. SQLite solo para tests locales con schema en memoria.
3. **Versiones de migración**: una por cada cambio de schema, numeradas, con downgrade incluido.

### Reconexión IB en Cambio de Modo

El `ChangeTradingModeUseCase` debe:
1. Validar que no hay posiciones abiertas antes de cambiar de puerto (especialmente live→paper)
2. Desconectar `IBKRClient` actual
3. Actualizar puerto en `control_settings`
4. Reconectar `IBKRClient` con nuevo puerto
5. Emitir `TradingModeSwitched` event

```python
class ChangeTradingModeUseCase:
    def execute(self, mode: TradingMode, confirmed_by: str) -> None:
        if mode == TradingMode.LIVE:
            open_trades = self._trade_repo.get_open()
            if open_trades:
                raise DomainError("No se puede cambiar a live con posiciones abiertas")
        new_port = 4001 if mode == TradingMode.LIVE else 4002
        self._state_repo.save_setting("ib_port", new_port)
        self._state_repo.save_setting("trading_mode", mode.value)
        self._broker.reconnect(port=new_port)
        self._event_bus.publish(TradingModeSwitched(old=self._current_mode, new=mode, by=confirmed_by))
```

### Dependency Injection sin frameworks externos

```python
# app/container.py
from functools import lru_cache

@lru_cache(maxsize=1)
def get_container() -> Container:
    engine = create_engine(settings.DATABASE_URL)
    trade_repo = SQLAlchemyTradeRepository(engine)
    broker = IBKRBrokerAdapter(get_ib_client())
    llm = OpenCodeLLMAdapter()
    notifications = TelegramNotificationAdapter()
    event_bus = EventBus()
    
    # Register handlers
    event_bus.subscribe(PositionClosed, PostmortemHandler(llm, trade_repo).handle)
    event_bus.subscribe(ControlSettingChanged, AuditLogHandler(engine).handle)
    
    return Container(
        trade_repo=trade_repo,
        broker=broker,
        llm=llm,
        notifications=notifications,
        event_bus=event_bus,
        place_order=PlaceOrderUseCase(trade_repo, broker, notifications, event_bus),
        close_position=ClosePositionUseCase(trade_repo, broker, notifications, event_bus),
        change_mode=ChangeTradingModeUseCase(trade_repo, broker, state_repo, event_bus),
    )
```

### Background Jobs — Tabla y Endpoints

```sql
CREATE TABLE background_jobs (
    id           TEXT PRIMARY KEY,
    job_type     TEXT NOT NULL,
    status       TEXT NOT NULL DEFAULT 'pending',
    params       TEXT,
    result       TEXT,
    error        TEXT,
    progress_pct INTEGER DEFAULT 0,
    progress_msg TEXT,
    created_at   TEXT NOT NULL,
    started_at   TEXT,
    completed_at TEXT
);
```

Endpoints async:
```
POST /jobs/llm-analysis  { symbol }     → { job_id }
POST /jobs/backtest      { symbol }     → { job_id }
GET  /jobs/{job_id}                     → { status, progress_pct, result?, error? }
GET  /jobs?type=llm-analysis&status=running
```

### Logging Estructurado

```python
import structlog
logger = structlog.get_logger()

# En cualquier use case:
logger.info("order_placed", symbol="AAPL", quantity=10, price=150.25, trade_id=42)
logger.error("llm_failed", symbol="TSLA", error=str(e), attempt=1)
```

Salida JSON compatible con `jq` para análisis en producción.

### Testing Strategy — Fixtures Clave

```python
# tests/conftest.py
@pytest.fixture
def engine():
    """SQLite in-memory para tests"""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()

@pytest.fixture
def mock_broker():
    return MockBrokerAdapter()  # no conecta a IB

@pytest.fixture
def container(engine, mock_broker):
    return Container(
        trade_repo=SQLAlchemyTradeRepository(engine),
        broker=mock_broker,
        llm=MockLLMAdapter(),
        notifications=MockNotificationAdapter(),
        event_bus=EventBus(),
        ...
    )
```

### Hardening de Subprocess OpenCode

```python
# infrastructure/llm/opencode_adapter.py
import re, subprocess, shlex
from pathlib import Path

SAFE_SYMBOL_RE = re.compile(r'^[A-Z0-9./=]{1,20}$')

class OpenCodeLLMAdapter(ILLMPort):
    def _call(self, prompt: str) -> str:
        bin_path = Path(settings.OPENCODE_BIN).resolve()
        if not bin_path.exists():
            raise RuntimeError(f"OpenCode binary not found: {bin_path}")
        result = subprocess.run(
            [str(bin_path), "run", "--model", settings.OPENCODE_MODEL, "--format", "json", prompt],
            capture_output=True, text=True, timeout=60,
            cwd=settings.OPENCODE_CWD,
        )
        if result.returncode != 0:
            raise LLMError(f"OpenCode failed: {result.stderr[:200]}")
        return self._parse_json_stream(result.stdout)
    
    def analyze_signal(self, signal: Signal) -> LLMDecision:
        if not SAFE_SYMBOL_RE.match(signal.symbol):
            raise ValueError(f"Invalid symbol: {signal.symbol}")
        prompt = self._build_prompt(signal)  # sin f-string con input externo
        return self._parse_decision(self._call(prompt))
```

### Model de Permisos `/control`

| Sección | Sin auth | Control Key | Admin Key |
|---------|----------|-------------|-----------|
| Ver todos los settings | ✓ | ✓ | ✓ |
| Cambiar parámetros de riesgo | | ✓ | ✓ |
| Añadir/rotar API keys | | | ✓ |
| Cambiar modo paper↔live | | | ✓ |
| Cambiar puertos IB | | | ✓ |
| Cambiar DB URL | | | ✓ |
| Aprobar símbolos | | | ✓ |
| Trigger job manual | | ✓ | ✓ |
| Reset circuit breaker | | ✓ | ✓ |
| Ver audit log | | ✓ | ✓ |

### Settings que requieren restart

| Setting | Hot-reload | Restart |
|---------|-----------|---------|
| `max_positions`, `max_risk_pct`, `capital_cap` | ✓ | |
| `paper_trading_only`, `require_human_approval` | ✓ | |
| `notification_level`, `circuit_breaker_threshold` | ✓ | |
| `ib_host`, `ib_port` | ✓ (reconexión automática) | |
| `telegram_bot_token` | | ✓ |
| `opencode_bin`, `opencode_model` | ✓ (siguiente llamada) | |
| `database_url` | | ✓ |
| `secret_encryption_key` | | ✓ |

---

## Success Criteria

- [ ] **Estado persistente**: modo, pausa y parámetros de riesgo sobreviven restart de la Raspberry Pi
- [ ] **Tests sin infra**: unit tests de use cases corren sin IB Gateway, Telegram ni DB real
- [ ] **Sin HTTP interno**: `loop.py` y `positions/manager.py` sin imports de `httpx` a localhost
- [ ] **Control plane completo**: cualquier parámetro operativo configurable desde `/control` sin tocar código
- [ ] **Audit trail**: todo cambio en `/control` registrado en `audit_log` con `changed_by` y timestamp
- [ ] **SQLAlchemy completo**: `database.py` monolítico eliminado; repositorios SQLAlchemy por entidad
- [ ] **Alembic**: `alembic upgrade head` aplica todas las migraciones limpiamente
- [ ] **PostgreSQL listo**: suite de tests pasa con `DATABASE_URL=postgresql://...`
- [ ] **API keys cifradas**: ninguna API key visible en plain text en DB ni en respuestas API
- [ ] **OpenCode consolidado**: 1 sola implementación de `_call_opencode()` en todo el codebase
- [ ] **Dashboard < 100ms**: `/dashboard/data` responde < 100ms con read model optimizado

---

## Related Modules

- **`app/db/database.py`**: Core del refactor — dividir en repositorios SQLAlchemy + migraciones Alembic
- **`app/api/main.py`**: Dividir en 6 route files; handlers delegan a use cases
- **`app/llm/loop.py`**: Eliminar HTTP interno; convertir en thin job wrapper
- **`app/positions/manager.py`**: Eliminar HTTP interno; usar `IBrokerPort`
- **`app/system/controller.py`**: Reemplazar con `PersistedSystemState` + use cases
- **`run.py`**: Slim down a ~50 LOC; lógica a `container.py` y `bootstrap/`

---

## Next Steps

1. ✓ Artefacto 01-design-concept.md completado
2. → Artefacto 02-persona-journey.md
3. Actualizar `.state/project-map.yaml` (phase_0 → complete)
4. `/clear` de contexto
5. `/120-architecture refactor`

---

## Sign-Off

| Rol | Nombre | Fecha | Aprobado |
|-----|--------|-------|----------|
| Developer/Operator | Frank Pacheco | 2026-05-14 | ✓ |

---

**Document Version**: 1.0  
**Last Updated**: 2026-05-14  
**Approved**: ✓ Yes
