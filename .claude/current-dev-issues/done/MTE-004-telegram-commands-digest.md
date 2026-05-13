# Issue MTE-004: Telegram Commands /notificaciones + /silencio + Digest Scheduler

**Module**: mtf-learning-engine
**Type**: AFK
**Effort**: S
**Blocked by**: None
**Requires review**: false

---

## WHY — The Human Problem

**User pain**: Frank no puede controlar cuánto le habla el bot. `NotificationPolicy` y `DigestGenerator` ya existen y funcionan, pero los comandos `/notificaciones` y `/silencio` no están registrados, y el digest no tiene job en el scheduler.

**Business impact**: Sin control de nivel de ruido, Frank ignora las notificaciones o las desactiva todas. El digest daría un resumen ordenado sin spam individual.

**Success signal**: Frank escribe `/notificaciones critico` y el bot confirma. A las 10:00 ET recibe el resumen automático sin haberlo pedido.

---

## WHO

| Persona | Role | Device | Environment | Goal | Constraint |
|---------|------|--------|-------------|------|------------|
| Frank Trader | Trader | iPhone/Telegram | Remoto | Control de ruido + resumen periódico | Comandos simples, no menús |

---

## WHAT — Constraints

- [ ] `NotificationPolicy` y `DigestGenerator` en `policy.py` NO se modifican — solo se exponen
- [ ] Comandos: `/notificaciones critico|normal|verbose` y `/silencio N` (horas)
- [ ] Digest enviado a 10:00 y 14:00 ET solo en días de mercado (Mon-Fri)
- [ ] Sin nuevas tablas DB — estado en memoria (ya implementado en policy.py)

---

## HOW — Implementation Approach

**`app/notifications/telegram_bot.py`** — agregar al final del archivo donde se registran los handlers:

```python
async def cmd_notificaciones(update, context):
    args = context.args
    nivel = args[0].lower() if args else "normal"
    niveles_validos = {"critico": "critical_only", "normal": "normal", "verbose": "verbose"}
    if nivel not in niveles_validos:
        await update.message.reply_text("Uso: /notificaciones critico|normal|verbose")
        return
    get_notification_policy().set_level(niveles_validos[nivel])
    await update.message.reply_text(f"Nivel de notificaciones: {niveles_validos[nivel]}")

async def cmd_silencio(update, context):
    from datetime import datetime, timedelta
    args = context.args
    horas = int(args[0]) if args else 1
    get_digest_generator().start_suppression()
    # Timer para restaurar
    import threading
    def restore():
        get_digest_generator().stop_suppression()
    threading.Timer(horas * 3600, restore).start()
    await update.message.reply_text(f"Silencio activado por {horas}h (solo críticos)")

# Registrar en build_application() o donde se agregan los handlers:
app.add_handler(CommandHandler("notificaciones", cmd_notificaciones))
app.add_handler(CommandHandler("silencio", cmd_silencio))
```

**`run.py`** — agregar job de digest:
```python
from app.notifications.policy import get_digest_generator
from app.db.database import get_open_trades, get_daily_pnl

def _send_digest():
    from app.notifications.telegram import notify
    open_trades = get_open_trades()
    daily_pnl = get_daily_pnl()
    digest_gen = get_digest_generator()
    msg = digest_gen.generate_digest(open_trades=open_trades, daily_pnl=daily_pnl)
    notify(msg)

scheduler.add_job(_send_digest, "cron", hour="10,14", minute=0, timezone=MARKET_TZ,
                  id="digest_job", replace_existing=True)
```

---

## Code Search

- [x] `app/notifications/policy.py` — `NotificationPolicy`, `DigestGenerator`, `get_notification_policy()`, `get_digest_generator()` — todos existen
- [x] `app/notifications/telegram_bot.py` — patrón de `CommandHandler` existente para copiar
- [x] `run.py` — patrón de `scheduler.add_job()` existente
- [x] `app/db/database.py` — `get_open_trades()`, `get_daily_pnl()` existen

**Reuse decision**:
- Reuse as-is: `NotificationPolicy`, `DigestGenerator`, `notify()`, `scheduler`, `get_open_trades()`
- Build new: handlers `cmd_notificaciones`, `cmd_silencio`, función `_send_digest()`

---

## Reference Documents

| Document | Path | What to Extract |
|----------|------|----------------|
| PRD | `docs/dev/artifacts/mtf-learning-engine/08-prd.md` | REQ-10, AC-10.1 a AC-10.5 |
| Issue original | `.claude/current-dev-issues/NS-003-policy-digest.md` | Spec original del módulo |

---

## Acceptance Criteria

- [ ] AC-10.1: `/notificaciones critico` → bot responde confirmando; señales ignoradas ya no llegan
- [ ] AC-10.2: `/notificaciones verbose` → señales ignoradas sí llegan
- [ ] AC-10.3: `/silencio 2` → no-críticos suprimidos 2h, luego restaurados automáticamente
- [ ] AC-10.4: Digest enviado a 10:00 ET en días de mercado (verificar en logs del scheduler)
- [ ] AC-10.5: Digest contiene: posiciones abiertas, P&L del día, última señal procesada

## Definition of Done

- [ ] Todos los ACs verificados manualmente en paper trading
- [ ] `pytest tests/notifications/test_policy.py` pasa
- [ ] Issue movido a `done/`
