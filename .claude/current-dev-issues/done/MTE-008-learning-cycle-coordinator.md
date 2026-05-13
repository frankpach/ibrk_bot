# Issue MTE-008: Learning Cycle Coordinator — app/ml/cycle.py

**Module**: mtf-learning-engine
**Type**: AFK
**Effort**: M
**Blocked by**: MTE-005, MTE-006
**Requires review**: false

---

## WHY — The Human Problem

**User pain**: El ReturnEvaluator calcula `future_return_7d/30d` pero nunca dispara el reentrenamiento. El rollback de parámetros no existe. Frank no sabe si el sistema está aprendiendo — no hay reporte de métricas.

**Business impact**: El loop de aprendizaje está roto en su última etapa. Los datos se acumulan en `candidate_decisions` sin retroalimentar nada. El sistema no mejora aunque tenga suficientes datos.

**Success signal**: Cada día a las 17:00 ET, `run_learning_cycle()` ejecuta, retrain el modelo si hay datos, verifica rollbacks, y Frank recibe un reporte en Telegram con AUC y win rates.

---

## WHO

| Persona | Role | Device | Environment | Goal | Constraint |
|---------|------|--------|-------------|------|------------|
| Frank Trader | Trader | iPhone/Telegram | Remoto | Saber que el sistema aprende | Reporte conciso, no spam |
| Motor Autónomo | Sistema | Raspberry Pi | Producción | Loop de aprendizaje cerrado | No bloquear scanner |

---

## WHAT — Constraints

- [ ] Archivo nuevo: `app/ml/cycle.py` — no modificar otros módulos excepto `run.py` para el scheduler
- [ ] `run_learning_cycle()` no bloquea el scanner — se ejecuta post-market
- [ ] Si cualquier paso falla → capturar en `LearningReport.errors` y continuar
- [ ] Notificación Telegram solo si AUC cambió > 0.05 o si hubo rollbacks — evitar spam diario

---

## HOW — Implementation Approach

**`app/ml/cycle.py`** (archivo nuevo, ~100 líneas):

```python
from dataclasses import dataclass, field
from datetime import datetime
import logging
from app.analysis.evaluator import run_return_evaluator
from app.ml.signal_filter import get_signal_filter
from app.db.database import get_closed_trades_with_snapshots, get_closed_trades_by_symbol
from app.db.database import get_or_create_symbol_parameters, update_symbol_parameters
from app.db.database import get_approved_symbols
from app.notifications.telegram import notify
import json

logger = logging.getLogger(__name__)

@dataclass
class LearningReport:
    date: str
    signal_filter_auc: float | None = None
    samples_used: int = 0
    symbols_rolled_back: list = field(default_factory=list)
    win_rates: dict = field(default_factory=dict)
    params_changed: dict = field(default_factory=dict)
    errors: list = field(default_factory=list)

    def to_telegram(self) -> str:
        lines = [f"📊 <b>Learning Report — {self.date}</b>"]
        if self.signal_filter_auc is not None:
            lines.append(f"🤖 SignalFilter AUC: {self.signal_filter_auc:.3f} ({self.samples_used} muestras)")
        if self.symbols_rolled_back:
            lines.append(f"⚠️ Rollbacks: {', '.join(self.symbols_rolled_back)}")
        if self.win_rates:
            top = sorted(self.win_rates.items(), key=lambda x: -x[1])[:5]
            wr_str = " | ".join(f"{s}:{v:.0%}" for s, v in top)
            lines.append(f"📈 Win rates: {wr_str}")
        if self.errors:
            lines.append(f"❌ Errores: {len(self.errors)}")
        return "\n".join(lines)


def run_learning_cycle(data_layer) -> LearningReport:
    report = LearningReport(date=datetime.utcnow().strftime("%Y-%m-%d"))

    # Paso 1: Evaluar returns pendientes
    try:
        run_return_evaluator(data_layer)
    except Exception as e:
        report.errors.append(f"ReturnEvaluator: {e}")

    # Paso 2: Retrain SignalFilter
    try:
        trades = get_closed_trades_with_snapshots(limit=200)
        if len(trades) >= 10:
            sf = get_signal_filter()
            auc = sf.retrain(trades)
            if isinstance(auc, float):
                report.signal_filter_auc = auc
                report.samples_used = len(trades)
    except Exception as e:
        report.errors.append(f"SignalFilter retrain: {e}")

    # Paso 3: Rollback y win_rates por símbolo
    try:
        symbols = get_approved_symbols()
        for symbol in symbols:
            try:
                rolled_back = maybe_rollback_parameters(symbol)
                if rolled_back:
                    report.symbols_rolled_back.append(symbol)
                wr = _get_win_rate_last_10(symbol)
                if wr is not None:
                    report.win_rates[symbol] = wr
            except Exception as e:
                report.errors.append(f"Symbol {symbol}: {e}")
    except Exception as e:
        report.errors.append(f"Symbol loop: {e}")

    # Paso 4: Notificar solo si hay algo relevante
    has_news = (report.signal_filter_auc is not None or
                report.symbols_rolled_back or
                report.errors)
    if has_news:
        try:
            notify(report.to_telegram())
        except Exception:
            pass

    return report


def maybe_rollback_parameters(symbol: str) -> bool:
    from app.db.database import get_closed_trades_by_symbol
    trades = get_closed_trades_by_symbol(symbol, limit=5)
    if len(trades) < 5:
        return False
    wins = sum(1 for t in trades if (t.pnl_pct or 0) > 0)
    if wins / 5 >= 0.30:
        return False
    params = get_or_create_symbol_parameters(symbol)
    if not params.previous_json:
        return False
    try:
        prev = json.loads(params.previous_json)
        update_symbol_parameters(symbol, **prev)
        notify(f"⚠️ <b>{symbol}</b>: parámetros revertidos (win_rate últimos 5: {wins}/5)")
        logger.info(f"Rolled back {symbol} parameters")
        return True
    except Exception as e:
        logger.error(f"Rollback failed for {symbol}: {e}")
        return False


def _get_win_rate_last_10(symbol: str) -> float | None:
    from app.db.database import get_closed_trades_by_symbol
    trades = get_closed_trades_by_symbol(symbol, limit=10)
    if len(trades) < 3:
        return None
    wins = sum(1 for t in trades if (t.pnl_pct or 0) > 0)
    return wins / len(trades)
```

**`run.py`** — agregar job diario:
```python
from app.ml.cycle import run_learning_cycle

scheduler.add_job(
    lambda: run_learning_cycle(get_data_layer()),
    "cron", hour=17, minute=0, timezone=MARKET_TZ,
    id="learning_cycle", replace_existing=True
)
```

---

## Code Search

- [x] `app/analysis/evaluator.py:9-68` — `run_return_evaluator()` leído
- [x] `app/ml/signal_filter.py` — `get_signal_filter()`, `retrain()` leídos
- [x] `app/db/database.py` — `get_approved_symbols()`, `get_or_create_symbol_parameters()` existen
- [x] `run.py` — patrón de `scheduler.add_job()` verificado

**Reuse decision**:
- Reuse as-is: `run_return_evaluator()`, `get_signal_filter()`, `get_closed_trades_with_snapshots()`, `notify()`
- Build new: `app/ml/cycle.py` completo, `maybe_rollback_parameters()`, `LearningReport`

---

## Reference Documents

| Document | Path | What to Extract |
|----------|------|----------------|
| PRD | `docs/dev/artifacts/mtf-learning-engine/08-prd.md` | REQ-06, REQ-07, AC-06.*, AC-07.* |
| Interface design | `docs/dev/artifacts/mtf-learning-engine/06-interface-design.md` | Flujo 3, LearningReport |

---

## Acceptance Criteria

- [ ] AC-06.1: `run_learning_cycle()` ejecuta sin excepción con 0 trades cerrados
- [ ] AC-06.2: Con 10+ trades con snapshots, `LearningReport.signal_filter_auc` es float > 0
- [ ] AC-06.3: `LearningReport.win_rates` contiene entry por símbolo con 3+ trades
- [ ] AC-06.4: Si retrain falla → `LearningReport.errors` tiene la descripción, ciclo continúa
- [ ] AC-06.5: Job registrado en scheduler a las 17:00 ET (verificar en logs de startup)
- [ ] AC-07.1: Win_rate últimos 5 < 30% + `previous_json` → parámetros revertidos
- [ ] AC-07.2: Rollback genera notificación Telegram
- [ ] AC-07.3: Con < 5 trades → no rollback
- [ ] AC-07.4: Sin `previous_json` → no rollback

## Definition of Done

- [ ] Todos los ACs verificados
- [ ] Tests unitarios para `maybe_rollback_parameters()` y `_get_win_rate_last_10()`
- [ ] Test de integración: `run_learning_cycle()` con datos mock completa sin error
- [ ] Issue movido a `done/`
