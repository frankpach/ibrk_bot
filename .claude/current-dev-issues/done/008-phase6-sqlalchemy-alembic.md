# Issue 008: Phase 6 — SQLAlchemy Models, Alembic y Repositorios

**Module**: refactor
**Type**: AFK
**Effort**: XL
**Blocked by**: 007
**Requires review**: false

---

## WHY — The Human Problem

**User pain**: `database.py` (1,277 LOC) es importado por 35 módulos. Cuando se modifica una query, es imposible saber qué partes del sistema se ven afectadas. Las migraciones de schema se hacen con `try/except ALTER TABLE` que no distingue "columna ya existe" de "error real". No hay forma de testear la capa de datos sin instanciar todo el sistema.

**Business impact**: Cada cambio de schema en producción puede fallar silenciosamente. La preparación para PostgreSQL es imposible mientras toda la lógica de datos viva en un único archivo con SQL específico de SQLite. La testabilidad de la capa de datos requiere un DB real.

**Success signal**: `grep -r "from app.db.database import" app/` devuelve 0 resultados. `alembic upgrade head` aplicado desde DB vacía crea el schema completo en < 5s. Tests de repositorio pasan con SQLite `:memory:`.

---

## WHO — The Users

| Persona | Role | Device | Environment | Goal | Constraint |
|---------|------|--------|-------------|------|------------|
| Frank | Developer | Desktop | Local | Cambiar el schema sin miedo a romper producción | Una sola persona — no hay red de seguridad |
| Frank | Developer | Terminal en Pi | Producción | Deploy con `alembic upgrade head` en < 5s | El sistema no puede estar caído durante la migración |

**Primary user**: Frank — Developer.

---

## WHAT — Constraints

**Architecture**:
- [ ] Los modelos SQLAlchemy están en `infrastructure/db/models/` — un archivo por modelo
- [ ] Los repositorios están en `infrastructure/db/repositories/` — uno por entidad
- [ ] Los repositorios implementan las interfaces de `application/ports/repository_port.py`
- [ ] `database.py` es eliminado al final de este issue — 0 referencias en `app/`
- [ ] Todas las migraciones incluyen `downgrade()` — no solo `upgrade()`
- [ ] Para operaciones complejas en SQLite (DROP COLUMN, ALTER TYPE): usar patrón rename-create-copy-drop

**Module-specific rules**:
- [ ] `get_session(engine)` context manager se usa para todas las operaciones transaccionales
- [ ] No hay raw SQL `f-strings` con variables interpoladas — usar parámetros bind
- [ ] El campo `updated_at` usa `onupdate=func.now()` en todos los modelos que lo tienen
- [ ] Los campos JSON usan `sqlalchemy.types.JSON` (compatible con SQLite y PostgreSQL)
- [ ] Los campos boolean usan `Boolean` (no `INTEGER` 0/1 de SQLite)

**Module context**:
- Archivos a crear: 17 model files, 8 repository files, Alembic migrations
- Archivo a eliminar: `app/db/database.py` (1,277 LOC)
- Archivos a actualizar: todos los que importaban `database.py` (35 módulos)

---

## HOW — Implementation Approach

**Fase 6 es la más grande del refactor — se puede hacer en sub-iteraciones:**

**Sub-iteración A — Setup SQLAlchemy + Alembic**:
1. Añadir `sqlalchemy`, `alembic` a `requirements.txt`
2. `alembic init infrastructure/db/migrations`
3. `env.py`: importar `Base.metadata` de todos los modelos
4. `alembic.ini`: usar `DATABASE_URL` de `control_settings` con fallback a `.env`
5. Crear `infrastructure/db/base.py` con `Base = DeclarativeBase()`

**Sub-iteración B — 17 SQLAlchemy Models**:

Para cada tabla existente en `database.py`:
```python
# infrastructure/db/models/trade.py
class TradeModel(Base):
    __tablename__ = "trades"
    id: Mapped[int] = mapped_column(primary_key=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(10), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="PENDING")
    trade_status: Mapped[str] = mapped_column(String(20), nullable=False, default="PENDING")
    quantity: Mapped[int] = mapped_column(nullable=True)
    entry_price: Mapped[float] = mapped_column(Float, nullable=True)
    stop_loss_price: Mapped[float] = mapped_column(Float, nullable=True)
    take_profit_price: Mapped[float] = mapped_column(Float, nullable=True)
    # ... resto de campos
    opened_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())
```

Modelos a crear: `TradeModel`, `SignalModel`, `SymbolConfigModel`, `SymbolParametersModel`, `DecisionModel`, `FeatureSnapshotModel`, `AccountSnapshotModel`, `NewsCacheModel`, `ScannerResultModel`, `AnalysisReportModel`, `MarketPermissionModel`, `PatternModel`, `DailyWatchlistModel`, `PositionSnapshotModel`, `ControlSettingModel`, `AuditLogModel`, `BackgroundJobModel`

**Sub-iteración C — Migración baseline**:
1. `alembic revision -m "001_initial_schema"`: captura el estado ACTUAL de la DB de producción
2. Migraciones `002` a `005`: añadir las 3 tablas nuevas + columna `updated_at` faltante
3. Verificar con DB de producción: `alembic upgrade head` desde el estado actual

**Sub-iteración D — 8 Repositorios SQLAlchemy**:

```python
# infrastructure/db/repositories/trade_repo.py
class SQLAlchemyTradeRepository(ITradeRepository):
    def __init__(self, engine: Engine): self._engine = engine
    
    def get_open(self) -> list[Trade]:
        with get_session(self._engine) as session:
            rows = session.query(TradeModel).filter(TradeModel.status == "OPEN").all()
            return [_row_to_trade(r) for r in rows]
    
    def save(self, trade: Trade) -> Trade:
        with get_session(self._engine) as session:
            model = TradeModel(**trade.to_dict())
            session.add(model)
            session.flush()
            return _row_to_trade(model)
    
    def close(self, trade_id: int, close: TradeClose) -> Trade:
        with get_session(self._engine) as session:
            model = session.get(TradeModel, trade_id)
            model.status = "CLOSED"
            model.exit_price = float(close.exit_price)
            model.pnl_usd = float(close.pnl_usd)
            # ...
            return _row_to_trade(model)
```

Repositorios: `SQLAlchemyTradeRepository`, `SQLAlchemySignalRepository`, `SQLAlchemySymbolRepository`, `SQLAlchemySystemStateRepository`, `SQLAlchemyAuditLogRepository`, `SQLAlchemyJobRepository`, `SQLAlchemyAccountRepository`, `SQLAlchemyPatternRepository`

**Sub-iteración E — Migrar los 35 módulos que importan database.py**:
1. Reemplazar `from app.db.database import get_open_trades` → inyectar `ITradeRepository`
2. Actualizar `container.py` para instanciar los repositorios SQLAlchemy
3. Al final: `rm app/db/database.py` — verificar que `grep -r "from app.db.database" app/` = 0

**Sub-iteración F — Tests parametrizados**:
```python
# tests/conftest.py
@pytest.fixture(params=["sqlite"])  # añadir "postgres" en Fase 7
def engine(request):
    if request.param == "sqlite":
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        yield engine
        engine.dispose()
```

**Events**:
- Publishes: none
- Consumes: none

---

## Code Search (MANDATORY)

- [x] `from app.db.database import`: 35 archivos — listarlos todos antes de empezar
- [x] SQL específico de SQLite en `database.py`: `AUTOINCREMENT`, `PRAGMA`, tipos TEXT usados como bool
- [x] `updated_at` en tablas actuales: pocas tablas lo tienen — añadir en migration
- [x] `sqlalchemy` en requirements: verificar si ya instalado

**Reuse decision**:
- Reuse as-is: schema actual (replicar en SQLAlchemy models, sin cambios de negocio)
- Extend: `container.py` (añadir instanciación de repositorios)
- Build new: 17 models, 8 repositories, Alembic setup, migration files
- Delete: `app/db/database.py`

---

## Reference Documents

| Document | Path | What to Extract |
|----------|------|----------------|
| PRD | `docs/dev/artifacts/refactor/08-prd.md` | RF-601 a RF-605 con ACs detallados |
| Architecture map | `docs/dev/artifacts/refactor/03-architecture-map.md` | Tabla completa de modelos existentes |
| Why Decisions | `docs/dev/artifacts/refactor/05-why-decisions.md` | DEC-001 (SQLAlchemy), DEC-002 (Alembic) |
| Constraints | `.claude/current-dev-issues/.state/constraints.md` | Reglas de Alembic en SQLite |

---

## Acceptance Criteria

- [ ] `grep -r "from app.db.database import" app/` → 0 resultados
- [ ] `alembic upgrade head` desde DB vacía → schema completo en < 5s
- [ ] `alembic downgrade base` → DB vacía sin error
- [ ] `alembic upgrade head` aplicado dos veces → idempotente (sin error)
- [ ] `SQLAlchemyTradeRepository.get_open()` devuelve trades con status="OPEN"
- [ ] `SQLAlchemyTradeRepository.save()` + `.close()` en test de integración con SQLite `:memory:`
- [ ] `SQLAlchemySystemStateRepository.get_setting("max_risk_pct")` devuelve el valor de `control_settings`
- [ ] `SQLAlchemyAuditLogRepository`: INSERT funciona, no hay UPDATE/DELETE
- [ ] Tests de repositorio pasan con SQLite `:memory:` (parámetro `sqlite` en fixture)
- [ ] El sistema funciona en producción tras la migración (smoke test post-deploy)

## Definition of Done

- [ ] Todos los acceptance criteria verificados
- [ ] `app/db/database.py` eliminado del codebase
- [ ] Test de integración completo: trade lifecycle (insert → update → close) via repositorio
- [ ] Test: `alembic upgrade head` aplicado a DB de producción SQLite sin pérdida de datos
- [ ] Mypy sin errores nuevos (SQLAlchemy tiene buenos type stubs)
- [ ] Issue movido a `done/`
