# Issue NS-003b: Telegram Commands + Digest Scheduler

**Module**: mtf-learning-engine (incorporado desde notification-system)
**Type**: AFK
**Effort**: S
**Blocked by**: ninguno
**Requires review**: false

---

## WHY — El Problema

`NotificationPolicy` y `DigestGenerator` ya existen en `app/notifications/policy.py` y funcionan. Pero los comandos de Telegram `/notificaciones` y `/silencio` no están registrados en el bot, y el job del digest no está en el scheduler. La funcionalidad existe pero no está expuesta.

**Success signal**: Frank escribe `/notificaciones critico` y el bot confirma el cambio. A las 10:00 ET recibe un digest automático con el estado del sistema.

---

## WHAT — Qué falta exactamente

- [ ] Registrar `CommandHandler("notificaciones", cmd_notificaciones)` en `app/notifications/telegram_bot.py`
- [ ] Registrar `CommandHandler("silencio", cmd_silencio)` en `app/notifications/telegram_bot.py`
- [ ] Implementar `cmd_notificaciones(update, context)` — parsea arg (critico/normal/verbose), llama `get_notification_policy().set_level()`
- [ ] Implementar `cmd_silencio(update, context)` — parsea horas, llama `get_digest_generator().start_suppression()` con timer
- [ ] Agregar APScheduler job en `run.py` para digest 10:00 y 14:00 ET:
  ```python
  scheduler.add_job(
      _send_digest, "cron",
      hour="10,14", minute=0, timezone=MARKET_TZ
  )
  ```
- [ ] Implementar `_send_digest()` que llama `get_digest_generator().generate_digest(open_trades, daily_pnl)` y envía via `notify()`

**NO tocar**: `NotificationPolicy`, `DigestGenerator` — ya están correctos.

---

## Archivos a modificar

| Archivo | Cambio |
|---------|--------|
| `app/notifications/telegram_bot.py` | +2 CommandHandlers, +2 funciones cmd_* |
| `run.py` | +1 scheduler.add_job para digest |

---

## Acceptance Criteria

- [ ] AC-01: `/notificaciones critico` → bot responde "Nivel cambiado a: critical_only"
- [ ] AC-02: `/notificaciones verbose` → señales ignoradas SÍ se notifican
- [ ] AC-03: `/silencio 2` → no-críticos suprimidos por 2 horas, luego se restauran
- [ ] AC-04: Digest enviado automáticamente a las 10:00 ET en días de mercado
- [ ] AC-05: Digest incluye: posiciones abiertas, P&L del día, señales procesadas

## Definition of Done

- [ ] Todos ACs verificados manualmente en paper trading
- [ ] Tests: cmd_notificaciones level change, cmd_silencio suppression, digest content
- [ ] Issue movido a `done/`
