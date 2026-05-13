# Issue MTE-006: Activar df_hourly en compute_features() + FeatureSet

**Module**: mtf-learning-engine
**Type**: AFK
**Effort**: S
**Blocked by**: MTE-005
**Requires review**: false

---

## WHY — The Human Problem

**User pain**: El pipeline ya fetcha datos horarios (`get_ohlcv("5 D", "1 hour")`) pero `compute_features()` los ignora completamente. Los indicadores horarios (RSI 1h, volumen 1h) son críticos para el timing de entrada — saber si el momentum intraday confirma la señal daily.

**Business impact**: El SignalFilter y el postmortem analizan señales sin saber si el RSI horario está sobrecomprado en el momento de entrada. Trades se abren en momentos subóptimos del día.

**Success signal**: `features.rsi_1h` tiene un valor float cuando hay datos horarios disponibles. El SignalFilter usa esas features adicionales para predicción.

---

## WHO

| Persona | Role | Device | Environment | Goal | Constraint |
|---------|------|--------|-------------|------|------------|
| Motor Autónomo | Sistema | Raspberry Pi | Producción | Timing de entrada con contexto horario | Fallback si hourly no disponible |

---

## WHAT — Constraints

- [ ] `compute_features()` firma no cambia — `df_hourly` ya es parámetro opcional
- [ ] Si `df_hourly` es None o tiene < 15 barras → `rsi_1h = None` (sin error)
- [ ] Migración DB via `_add_column_if_missing()` para las 2 columnas nuevas
- [ ] `_extract_features()` del SignalFilter agrega `rsi_1h` y `volume_ratio_1h` con defaults

---

## HOW — Implementation Approach

**`app/analysis/indicators.py` — en `compute_features()`**:

```python
# Agregar al FeatureSet después de los cálculos daily:
if df_hourly is not None and len(df_hourly) >= 15:
    fs.rsi_1h = _compute_rsi(df_hourly)
    fs.volume_ratio_1h = _compute_volume_ratio(df_hourly)
```

**`app/analysis/indicators.py` — FeatureSet dataclass**:
```python
rsi_1h: Optional[float] = None
volume_ratio_1h: Optional[float] = None
weekly_trend: Optional[str] = None  # preparar para MTE-007
```

**`app/db/database.py` — en `init_analysis_tables()`**:
```python
_add_column_if_missing(conn, "feature_snapshots", "rsi_1h", "REAL")
_add_column_if_missing(conn, "feature_snapshots", "volume_ratio_1h", "REAL")
_add_column_if_missing(conn, "feature_snapshots", "weekly_trend", "TEXT")
```

**`app/db/database.py` — en `insert_feature_snapshot()`**:
Agregar `rsi_1h` y `volume_ratio_1h` al INSERT (con `.get()` para backwards compat).

**`app/ml/signal_filter.py` — en `_extract_features()`**:
```python
def _extract_features(self, features) -> list:
    return [
        getattr(features, 'rsi_14', 50) or 50,
        getattr(features, 'macd_line', 0) or 0,
        getattr(features, 'atr_pct', 2.0) or 2.0,
        getattr(features, 'volume_ratio_20d', 1.0) or 1.0,
        getattr(features, 'bollinger_position', 0.5) or 0.5,
        getattr(features, 'rs_vs_spy_30d', 0) or 0,
        getattr(features, 'day_of_week', 0) or 0,
        getattr(features, 'hour', 10) or 10,
        getattr(features, 'rsi_1h', 50) or 50,           # NUEVO
        getattr(features, 'volume_ratio_1h', 1.0) or 1.0, # NUEVO
    ]
```

**Nota**: Aumentar a 10 features rompe compatibilidad con el modelo pkl existente. Al hacer retrain (MTE-005 ya debe estar hecho), el nuevo modelo se entrena con 10 features automáticamente.

---

## Code Search

- [x] `app/analysis/indicators.py:176-245` — `compute_features()` leído
- [x] `app/analysis/indicators.py:17-51` — `FeatureSet` dataclass leído
- [x] `app/ml/signal_filter.py:55-66` — `_extract_features()` leído (8 features actual)
- [x] `app/db/database.py:715-736` — `insert_feature_snapshot()` leído

**Reuse decision**:
- Reuse as-is: `_compute_rsi()`, `_compute_volume_ratio()` — exactamente las mismas funciones, aplicadas a df_hourly
- Extend: `FeatureSet`, `compute_features()`, `_extract_features()`, `insert_feature_snapshot()`

---

## Reference Documents

| Document | Path | What to Extract |
|----------|------|----------------|
| PRD | `docs/dev/artifacts/mtf-learning-engine/08-prd.md` | REQ-04, AC-04.1 a AC-04.4 |
| Architecture map | `docs/dev/artifacts/mtf-learning-engine/03-architecture-map.md` | GAP-04 |

---

## Acceptance Criteria

- [ ] AC-04.1: Con `df_hourly` válido (15+ barras), `features.rsi_1h` es float entre 0 y 100
- [ ] AC-04.2: Con `df_hourly = None` → `features.rsi_1h is None` (no crashea)
- [ ] AC-04.3: `insert_feature_snapshot()` persiste `rsi_1h` y `volume_ratio_1h` en DB
- [ ] AC-04.4: `_extract_features()` del SignalFilter retorna lista de 10 elementos
- [ ] AC-04.5: `pytest tests/analysis/test_data.py` pasa sin regresiones

## Definition of Done

- [ ] Todos los ACs verificados
- [ ] Tests de `compute_features()` actualizados para verificar `rsi_1h`
- [ ] Issue movido a `done/`
