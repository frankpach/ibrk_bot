# Issue NS-001: NotificationThrottler + NotificationQueue

**Module**: notification-system
**Type**: AFK
**Effort**: M
**Blocked by**: —
**Requires review**: false

---

## WHY — The Human Problem

**User pain**: Frank recibe 1000 mensajes idénticos del circuit breaker cada 2 minutos. El sistema no tiene memoria de lo que ya comunicó.

**Business impact**: Frank ignora o silencia el bot. Las notificaciones críticas se pierden en el ruido. La confianza en el sistema se destruye.

**Success signal**: Circuit breaker se activa una vez y Frank lo ve. Nunca recibe duplicados.

---

## WHO

| Persona | Role | Device | Environment | Goal | Constraint |
|---|---|---|---|---|---|
| Frank | Trader | iPhone | Telegram | Recibir solo información nueva y relevante | No quiere configurar reglas complejas |
| Sistema | Bot | Pi | 24/7 | Notificar sin repetir | No DB pesada, no bloquear threads |

**Primary user**: Frank.

---

## WHAT — Constraints

- [ ] `NotificationThrottler` con dict en memoria: `{(message_type, content_hash): last_sent_at}`
- [ ] Reglas de throttle por tipo (ver PRD REQ-01)
- [ ] `NotificationQueue`: daemon thread + `queue.Queue`
- [ ] Thread-safe: cualquier thread puede encolar, el daemon entrega
- [ ] Graceful shutdown: vaciar cola antes de salir
- [ ] Retry: 1 reintento a los 5s si Telegram falla, luego drop

**Module-specific rules**:
- [ ] No modificar IBKRClient
- [ ] No agregar tablas DB (in-memory only)
- [ ] `notify()` existente debe seguir funcionando como wrapper

---

## HOW — Implementation Approach

**app/notifications/throttler.py**:
```python
class NotificationThrottler:
    THROTTLE_RULES = {
        "circuit_breaker": {"once_per_activation": True},
        "position_closed": {"once_per_content_hash": True},
        "ib_disconnected": {"once_per_event": True},
        "digest": {"no_throttle": True},
    }
    
    def notify_if_changed(self, message_type, content, content_hash=None, force=False) -> bool: ...
    def reset_state(self, message_type) -> None: ...
```

**app/notifications/queue.py**:
```python
class NotificationQueue:
    def start(self) -> None: ...
    def stop(self) -> None: ...
    def enqueue(self, content: str) -> None: ...
```

**app/notifications/telegram.py** (modificar):
- `notify()` ahora usa `throttler.notify_if_changed("generic", content, force=True)`
- O crea una función nueva `notify_throttled()` y deja `notify()` como alias

---

## Code Search

- [ ] `app/notifications/telegram.py` — función `notify()` a envolver
- [ ] `app/system/controller.py` — llama `notify()` en circuit breaker
- [ ] `app/positions/manager.py` — llama `notify()` al cerrar posición
- [ ] `app/llm/loop.py` — llama `notify()` en señales
- [ ] `python-telegram-bot` — Bot.send_message para el thread

**Reuse decision**:
- Reuse as-is: `Bot` instance, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`
- Build new: `NotificationThrottler`, `NotificationQueue`
- Extend: `notify()` como wrapper

---

## Reference Documents

| Document | Path | What to Extract |
|---|---|---|
| PRD | docs/dev/artifacts/notification-system/08-prd.md | REQ-01, REQ-02, REQ-06 |
| Interface design | docs/dev/artifacts/notification-system/06-interface-design.md | NotificationThrottler, NotificationQueue |

---

## Acceptance Criteria

- [ ] AC-01.1: Dos `notify_if_changed("circuit_breaker", ...)` seguidos → solo 1 mensaje Telegram
- [ ] AC-01.2: `reset_state("circuit_breaker")` → siguiente notificación sí se envía
- [ ] AC-01.3: `position_closed` con mismo content_hash → solo 1 vez
- [ ] AC-02.1: `notify()` llamado desde thread APScheduler → no crash, mensaje llega
- [ ] AC-02.2: 50 notificaciones en 2 segundos → todas entregan (cola + rate limit)
- [ ] AC-06.1: `controller.py`, `positions/manager.py`, `llm/loop.py` sin cambios
- [ ] AC-06.2: Tests existentes pasan sin modificación

## Definition of Done

- [ ] Todos ACs verificados
- [ ] Tests nuevos: throttler dedup, queue thread-safety, graceful shutdown
- [ ] Issue movido a `done/`
