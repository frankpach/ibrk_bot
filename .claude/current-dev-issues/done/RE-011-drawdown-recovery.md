# Issue RE-011: Drawdown Recovery Strategy

**Module**: risk-engine-v2
**Type**: AFK
**Effort**: M
**Blocked by**: RE-001
**Requires review**: false

---

## WHY — The Human Problem

**User pain**: Si el sistema pierde 10% en una semana, solo hay circuit breaker (pausa). No hay plan de recuperación.

**Business impact**: Capital estancado en pausa sin estrategia de cómo salir del hoyo. Frank no sabe cuándo reanudar con seguridad.

**Success signal**: Sistema adapta automáticamente según drawdown: reduce size, aumenta calidad de señales, o pausa completamente.

---

## WHAT — Constraints

- [ ] Niveles de drawdown:
  - < 5%: operar normal
  - 5-10%: size × 0.5, solo STRONG signals
  - 10-15%: pausa 24h, revisar post-mortem
  - > 15%: solo paper trading hasta validación manual
- [ ] Recuperación progresiva: cuando P&L vuelve a -5%, reactivar normal
- [ ] Notificar a Frank del estado de recuperación
- [ ] Guardar estado en DB para sobrevivir reinicios

---

## HOW — Implementation Approach

**app/risk/recovery.py**:
```python
class DrawdownRecovery:
    THRESHOLDS = {
        "normal": 0.05,
        "cautious": 0.10,
        "pause": 0.15,
        "paper_only": 0.20,
    }
    
    def get_mode(self, drawdown_pct: float) -> str: ...
    def get_adjustments(self, drawdown_pct: float) -> dict: ...
```

**app/system/controller.py**:
```python
def check_drawdown(self, daily_pnl, capital):
    drawdown = self.calculate_drawdown()
    mode = recovery.get_mode(drawdown)
    if mode == "pause":
        self.pause()
        notify(f"Drawdown {drawdown:.1%}. Pausa 24h.")
```

---

## Acceptance Criteria

- [ ] AC-01: Drawdown 7% → size × 0.5, solo STRONG
- [ ] AC-02: Drawdown 12% → pausa automática 24h
- [ ] AC-03: Drawdown 18% → solo paper trading
- [ ] AC-04: Recuperación a -4% → modo normal restaurado

## Definition of Done

- [ ] Todos ACs verificados
- [ ] Tests: drawdown levels, mode transitions, recovery
- [ ] Issue movido a `done/`
