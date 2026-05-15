# Issue 009: Phase 7 — Migrar a PostgreSQL

**Module**: refactor
**Type**: HITL
**Effort**: M
**Blocked by**: 008
**Requires review**: true

---

## WHY — The Human Problem

**User pain**: SQLite tiene limitaciones de concurrencia (un solo writer a la vez), no soporta operaciones avanzadas de Alembic, y no escala si el sistema crece a más símbolos, más frecuencia de signals, o si se quiere exponer datos a herramientas de análisis externas.

**Business impact**: Todas las fases anteriores han preparado la arquitectura para este momento. El salto a PostgreSQL es la culminación del trabajo de repos SQLAlchemy + Alembic. Sin este paso, el sistema sigue corriendo sobre SQLite con sus limitaciones.

**Success signal**: `GET /control/settings/database_url` devuelve una URL de PostgreSQL. El dashboard muestra los datos correctamente desde PostgreSQL. Los datos históricos de SQLite están disponibles.

---

## WHO — The Users

| Persona | Role | Device | Environment | Goal | Constraint |
|---------|------|--------|-------------|------|------------|
| Frank | Developer | Terminal Pi | Producción | Migrar datos sin pérdida y sin downtime prolongado | El sistema en producción no puede estar caído más de 5 min |

**Primary user**: Frank — Developer.

---

## WHAT — Constraints

**Architecture**:
- [ ] La migración de datos usa `scripts/migrate_to_postgres.py` — no edición manual de DB
- [ ] El script de migración tiene modo `--dry-run` que verifica row counts sin escribir
- [ ] La ventana de mantenimiento es: parar app → migrar datos → cambiar `database_url` → reiniciar
- [ ] El rollback es claro: cambiar `database_url` de vuelta a SQLite → reiniciar
- [ ] PostgreSQL se instala en la Raspberry Pi (o en host separado) ANTES de este issue

**Module-specific rules**:
- [ ] `alembic upgrade head` se corre contra PostgreSQL ANTES de migrar los datos
- [ ] La verificación incluye: row counts por tabla + checksum de campos críticos (trade id, symbol, pnl)
- [ ] SQLite backup se retiene 30 días tras la migración exitosa
- [ ] El campo `database_url` en `control_settings` apunta al PostgreSQL tras el deploy

**Module context**:
- Archivos nuevos: `scripts/migrate_to_postgres.py`, `scripts/verify_migration.py`
- Sin cambios en código de aplicación (los repositorios SQLAlchemy ya son agnósticos al backend)

---

## HOW — Implementation Approach

**Script de migración** (RF-701):
```python
# scripts/migrate_to_postgres.py
def migrate(sqlite_url: str, pg_url: str, dry_run: bool = False):
    sqlite_engine = create_engine(sqlite_url)
    pg_engine = create_engine(pg_url)
    
    tables = [TradeModel, SignalModel, SymbolConfigModel, ...]
    
    for model in tables:
        rows = sqlite_session.query(model).all()
        if not dry_run:
            pg_session.bulk_save_objects([model(**r.__dict__) for r in rows])
        
        print(f"{model.__tablename__}: {len(rows)} rows {'(dry-run)' if dry_run else 'migrated'}")
    
    if not dry_run:
        verify_checksums(sqlite_engine, pg_engine)
```

**Verificación** (RF-701):
```python
# scripts/verify_migration.py
def verify_checksums(sqlite_engine, pg_engine):
    for table in TABLES:
        sqlite_count = sqlite_session.query(func.count()).from_table(table).scalar()
        pg_count = pg_session.query(func.count()).from_table(table).scalar()
        assert sqlite_count == pg_count, f"Row count mismatch: {table} {sqlite_count} vs {pg_count}"
        print(f"{table}: {sqlite_count} rows ✓")
```

**Procedimiento de migración en producción**:
1. `pip install psycopg` (driver PostgreSQL)
2. Instalar PostgreSQL en Pi: `sudo apt install postgresql`
3. Crear DB: `createdb ibkr_trader`
4. `alembic upgrade head` contra PostgreSQL (`DATABASE_URL=postgresql://...`)
5. `python scripts/migrate_to_postgres.py --dry-run` — verificar counts
6. **Ventana de mantenimiento** (< 5 min):
   - `systemctl stop ibkr-trader`
   - `python scripts/migrate_to_postgres.py` — migrar datos
   - `python scripts/verify_migration.py` — verificar
   - Cambiar `database_url` en `control_settings` (o editar `.env` como bootstrap)
   - `systemctl start ibkr-trader`
7. Verificar dashboard funciona con datos desde PostgreSQL
8. Retener `ibkr_trader.db` como backup por 30 días

**Actualizar `container.py`** (RF-702):
- Pasar `DATABASE_URL` de `control_settings` al engine SQLAlchemy
- Si PostgreSQL, usar `pool_size=5, max_overflow=10`
- Si SQLite, usar `connect_args={"check_same_thread": False}`

**Tests parametrizados con PostgreSQL**:
```python
@pytest.fixture(params=["sqlite", "postgres"])
def engine(request):
    if request.param == "postgres":
        pg_url = os.environ.get("TEST_PG_URL")
        if not pg_url:
            pytest.skip("TEST_PG_URL not set")
        engine = create_engine(pg_url)
    else:
        engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)
    engine.dispose()
```

**Events**:
- Publishes: none
- Consumes: none

---

## Code Search (MANDATORY)

- [x] `PRAGMA` en codebase: verificar que Issue 008 los eliminó
- [x] `AUTOINCREMENT` en SQL: verificar eliminado
- [x] `connect_args={"check_same_thread": False}`: reemplazar por pool config de PostgreSQL
- [x] `psycopg` o `psycopg2` en requirements: añadir si no existe

**Reuse decision**:
- Reuse as-is: todos los repositorios SQLAlchemy (Issue 008) — ya son agnósticos al backend
- Extend: `container.py` — añadir pool config diferente por backend
- Build new: `migrate_to_postgres.py`, `verify_migration.py`

---

## Reference Documents

| Document | Path | What to Extract |
|----------|------|----------------|
| PRD | `docs/dev/artifacts/refactor/08-prd.md` | RF-701, RF-702, edge cases de DB inaccesible |
| Interface design | `docs/dev/artifacts/refactor/06-interface-design.md` | Workflow 5 (migración DB URL) |
| Why Decisions | `docs/dev/artifacts/refactor/05-why-decisions.md` | DEC-001, DEC-002 (SQLAlchemy/Alembic rationale) |

---

## Acceptance Criteria

- [ ] `python scripts/migrate_to_postgres.py --dry-run` completa sin errores sobre DB de producción
- [ ] Row counts verificados: todas las tablas coinciden entre SQLite y PostgreSQL
- [ ] App arranca con `DATABASE_URL=postgresql://...` sin errores
- [ ] `GET /dashboard/data` devuelve datos correctos desde PostgreSQL
- [ ] `GET /trades` devuelve trades históricos migrados
- [ ] `pytest -k postgres tests/integration/` pasa con `TEST_PG_URL` configurado
- [ ] Backup SQLite existe y tiene el mismo row count que PostgreSQL
- [ ] Downtime total durante la migración < 5 minutos

## Definition of Done

- [ ] Todos los acceptance criteria verificados
- [ ] `scripts/migrate_to_postgres.py` y `scripts/verify_migration.py` commitados
- [ ] `requirements.txt` incluye `psycopg` (o `psycopg2-binary`)
- [ ] Tests de integración con PostgreSQL pasan en CI local
- [ ] Backup SQLite nombrado con fecha: `ibkr_trader_backup_2026MMDD.db`
- [ ] Code review aprobado (HITL — impacto en datos de producción)
- [ ] Issue movido a `done/`
