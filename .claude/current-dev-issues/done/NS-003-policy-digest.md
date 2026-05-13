# Issue NS-003: NotificationPolicy + Digest + Commands

**Module**: notification-system
**Type**: AFK
**Effort**: S
**Blocked by**: NS-001
**Requires review**: false

---

## WHY — The Human Problem

**User pain**: Frank no puede controlar cuánto le habla el bot. En algunos momentos quiere silencio total, en otros quiere saber todo.

**Business impact**: Sin control de nivel de notificación, Frank o desactiva el bot o ignora todo. No hay punto medio.

**Success signal**: Frank escribe `/notificaciones critico` y solo recibe circuit breakers, cierres y errores fatales.

---

## WHO

| Persona | Role | Device | Environment | Goal | Constraint |
|---|---|---|---|---|---|
| Frank | Trader | iPhone | Telegram | Ajustar nivel de ruido según contexto | Comandos simples, no menús complejos |

---

## WHAT — Constraints

- [ ] Tres niveles: `critical_only`, `normal`, `verbose`
- [ ] Configurable vía `settings.NOTIFICATION_LEVEL` (default `normal`)
- [ ] Override runtime vía comandos Telegram: `/notificaciones critico|normal|verbose`
- [ ] Daily digest cada 4h en horario mercado (10:00, 14:00 ET)
- [ ] Comando `/silencio HH` para silenciar todo excepto crítico por N horas
- [ ] Durante digest window (5 min), alertas individuales no críticas se suprimen

**Module-specific rules**:
- [ ] Sin tablas DB adicionales (in-memory state)
- [ ] Cambio de nivel sin reinicio

---

## HOW — Implementation Approach

**app/notifications/policy.py**:
```python
class NotificationPolicy:
    LEVELS = {
        "critical_only": {"circuit_breaker", "position_closed", "fatal_error", "approval_request"},
        "normal": {"critical_only"} | {"position_opened", "ib_disconnected", "ib_reconnected", "digest"},
        "verbose": "all",
    }
    
    def should_notify(self, message_type: str) -> bool: ...
```

**app/notifications/digest.py**:
```python
def generate_digest() -> str: ...
```

**app/notifications/telegram_bot.py**:
- Agregar handlers:
```python
app.add_handler(CommandHandler("notificaciones", cmd_notificaciones))
app.add_handler(CommandHandler("silencio", cmd_silencio))
```

**run.py**:
- Agregar APScheduler job para digest:
```python
scheduler.add_job(generate_and_send_digest, "cron", hour="10,14", minute=0, timezone=MARKET_TZ)
```

---

## Code Search

- [ ] `app/notifications/telegram_bot.py` — agregar comandos
- [ ] `app/config/settings.py` — agregar `NOTIFICATION_LEVEL`
- [ ] `run.py` — patrón de scheduler.add_job
- [ ] `app/db/database.py` — `get_open_trades`, `get_daily_pnl` para digest

**Reuse decision**:
- Reuse as-is: APScheduler, `notify()`, `get_open_trades()`
- Build new: `NotificationPolicy`, digest generator, comandos Telegram

---

## Reference Documents

| Document | Path | What to Extract |
|---|---|---|
| PRD | docs/dev/artifacts/notification-system/08-prd.md | REQ-03, REQ-05 |
| Interface design | docs/dev/artifacts/notification-system/06-interface-design.md | NotificationPolicy, digest workflow |

---

## Acceptance Criteria

- [ ] AC-03.1: `/notificaciones critico` → `signal_ignored` NO se envía
- [ ] AC-03.2: `/notificaciones verbose` → `signal_ignored` SÍ se envía
- [ ] AC-03.3: Cambio de nivel sin reinicio
- [ ] AC-05.1: Digest enviado a 10:00 ET
- [ ] AC-05.2: Durante digest, `position_opened` se retrasa 5 min

## Definition of Done

- [ ] Todos ACs verificados
- [ ] Tests nuevos: policy levels, digest generation, silencio command
- [ ] Issue movido a `done/`
