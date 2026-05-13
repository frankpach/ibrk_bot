# Issue MTE-005: Fix SignalFilter.retrain() + Migración DB feature_snapshot_id

**Module**: mtf-learning-engine
**Type**: AFK
**Effort**: M
**Blocked by**: None
**Requires review**: false

---

## WHY — The Human Problem

**User pain**: El sistema de ML nunca ha aprendido nada real desde que existe. `SignalFilter.retrain()` busca `trade.features` — campo que no existe en el dataclass `Trade`. El dataset siempre está vacío y el sistema opera con reglas heurísticas fijas.

**Business impact**: El filtro de señales no mejora con el tiempo. Señales débiles que deberían rechazarse llegan al LLM. El capital se expone a trades de baja calidad que un modelo entrenado rechazaría.

**Success signal**: Después del fix, `retrain()` carga features reales desde la DB, produce un modelo con AUC medible (> 0.5), y el AUC aparece en los logs y en el `LearningReport`.

---

## WHO

| Persona | Role | Device | Environment | Goal | Constraint |
|---------|------|--------|-------------|------|------------|
| Frank Developer | Quant | Desktop | Home office | ML que aprende de verdad | No romper trades en curso |
| Motor Autónomo | Sistema | Raspberry Pi | Producción | SignalFilter con modelo real | Fallback graceful si falla |

---

## WHAT — Constraints

- [ ] La migración de DB usa `_add_column_if_missing()` — nunca `ALTER TABLE` directo
- [ ] `trades` existentes (sin `feature_snapshot_id`) se omiten en retrain silenciosamente — no error
- [ ] El modelo pkl sigue en `models/signal_filter.pkl` — no cambiar path
- [ ] `TimeSeriesSplit(n_splits=5)` obligatorio — no split aleatorio
- [ ] Mínimo 10 muestras para entrenar; si < 10 → retornar False y loggear
- [ ] Si sklearn no está disponible → retornar False (ya existe este check)

---

## HOW — Implementation Approach

### Paso 1: Migración DB (`app/db/database.py`)

En `init_analysis_tables()`, agregar:
```python
_add_column_if_missing(conn, "trades", "feature_snapshot_id", "INTEGER")
```

Nueva función:
```python
def get_feature_snapshot_by_id(snapshot_id: int) -> dict | None:
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM feature_snapshots WHERE id=?", (snapshot_id,)
    ).fetchone()
    conn.close()
    if row is None:
        return None
    return dict(row)
```

Nueva función para retrain:
```python
def get_closed_trades_with_snapshots(limit: int = 200) -> list:
    """Retorna trades cerrados que tienen feature_snapshot_id."""
    conn = get_connection()
    rows = conn.execute(
        """SELECT t.*, fs.rsi_14, fs.macd_line, fs.atr_pct, fs.volume_ratio_20d,
                  fs.bollinger_position, fs.rs_vs_spy_30d
           FROM trades t
           JOIN feature_snapshots fs ON t.feature_snapshot_id = fs.id
           WHERE t.status = 'CLOSED'
           ORDER BY t.closed_at DESC
           LIMIT ?""",
        (limit,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]
```

### Paso 2: Fix retrain() (`app/ml/signal_filter.py`)

```python
def retrain(self, trades: list) -> float | bool:
    try:
        from sklearn.linear_model import LogisticRegression
        from sklearn.preprocessing import StandardScaler
        from sklearn.model_selection import TimeSeriesSplit, cross_val_score
        from app.db.database import get_feature_snapshot_by_id

        X, y = [], []
        for trade in trades:
            # Soportar tanto dict (de get_closed_trades_with_snapshots)
            # como objeto Trade con feature_snapshot_id
            if isinstance(trade, dict):
                snap = trade  # ya tiene los campos del JOIN
                pnl = trade.get("pnl_pct", 0) or 0
            else:
                snap_id = getattr(trade, "feature_snapshot_id", None)
                if not snap_id:
                    continue
                snap = get_feature_snapshot_by_id(snap_id)
                if snap is None:
                    continue
                pnl = getattr(trade, "pnl_pct", 0) or 0

            X.append(self._extract_features(snap))
            y.append(1 if pnl > 0 else 0)

        if len(X) < 10:
            logger.warning(f"Not enough data to retrain: {len(X)} samples")
            return False

        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)

        # Evaluar con TimeSeriesSplit
        model_eval = LogisticRegression(max_iter=1000)
        tscv = TimeSeriesSplit(n_splits=min(5, len(X) // 2))
        try:
            auc_scores = cross_val_score(model_eval, X_scaled, y, cv=tscv, scoring="roc_auc")
            auc = float(auc_scores.mean())
        except Exception:
            auc = 0.5  # fallback si CV falla (p.ej. una sola clase)

        # Entrenar modelo final sobre todos los datos
        model = LogisticRegression(max_iter=1000)
        model.fit(X_scaled, y)

        Path(self.model_path).parent.mkdir(parents=True, exist_ok=True)
        with open(self.model_path, "wb") as f:
            pickle.dump({"model": model, "scaler": scaler}, f)

        self._model = model
        self._scaler = scaler
        logger.info(f"Model retrained with {len(X)} samples. CV AUC: {auc:.3f}")
        return auc

    except ImportError:
        logger.warning("scikit-learn not available")
        return False
    except Exception as e:
        logger.error(f"Retraining failed: {e}")
        return False
```

### Paso 3: Vincular feature_snapshot_id al insertar trade (`app/api/main.py`)

Al llamar `insert_trade()` después del fill, incluir el `feature_snapshot_id` si existe en el contexto del análisis:
```python
# El feature_snapshot_id viene del AnalysisPipeline result
insert_trade(Trade(..., feature_snapshot_id=analysis_result.feature_snapshot_id))
```

---

## Code Search

- [x] `app/ml/signal_filter.py:118-168` — retrain() actual leído
- [x] `app/db/database.py:715-736` — `insert_feature_snapshot()` leído
- [x] `app/db/database.py:75-82` — `_add_column_if_missing()` disponible
- [x] `app/db/models.py:27-55` — Trade dataclass sin feature_snapshot_id confirmado

**Reuse decision**:
- Reuse as-is: `_add_column_if_missing()`, `insert_feature_snapshot()`, `SignalFilter` skeleton
- Extend: `retrain()`, `Trade` dataclass (columna nueva), `init_analysis_tables()`
- Build new: `get_feature_snapshot_by_id()`, `get_closed_trades_with_snapshots()`

---

## Reference Documents

| Document | Path | What to Extract |
|----------|------|----------------|
| PRD | `docs/dev/artifacts/mtf-learning-engine/08-prd.md` | REQ-01, AC-01.1 a AC-01.5 |
| Architecture map | `docs/dev/artifacts/mtf-learning-engine/03-architecture-map.md` | GAP-01 |
| Why Decisions | `docs/dev/artifacts/mtf-learning-engine/05-why-decisions.md` | WD-05 |

---

## Acceptance Criteria

- [ ] AC-01.1: Con 10+ trades con `feature_snapshot_id`, `retrain()` retorna un float AUC > 0
- [ ] AC-01.2: Con < 10 muestras → retorna False, logea warning
- [ ] AC-01.3: `models/signal_filter.pkl` se actualiza tras retrain exitoso
- [ ] AC-01.4: `retrain()` usa `TimeSeriesSplit` — verificable en logs ("CV AUC: X.XXX")
- [ ] AC-01.5: Trade sin `feature_snapshot_id` → omitido silenciosamente (no crashea)
- [ ] AC-01.6: `get_feature_snapshot_by_id(999)` → retorna None sin error
- [ ] AC-01.7: `pytest tests/ml/test_signal_filter.py` pasa sin regresiones

## Definition of Done

- [ ] Todos los ACs verificados
- [ ] `pytest tests/ml/test_signal_filter.py` pasa
- [ ] `pytest tests/db/test_database.py` pasa
- [ ] Issue movido a `done/`
