# Issue NS-002: ApprovalManager (Async Callbacks)

**Module**: notification-system
**Type**: AFK
**Effort**: M
**Blocked by**: NS-001
**Requires review**: false

---

## WHY — The Human Problem

**User pain**: Cuando el sistema pide aprobación de una orden, un thread de APScheduler se bloquea por 5 minutos haciendo polling. El bot de Telegram no puede responder a otros comandos durante ese tiempo.

**Business impact**: El sistema parece "congelado". Si Frank toca "Aprobar", la respuesta puede llegar tarde o perderse. Ordenes potencialmente rentables se cancelan por timeout innecesario.

**Success signal**: Frank toca "Aprobar" y la orden se ejecuta en menos de 3 segundos. El sistema sigue funcionando normalmente mientras espera.

---

## WHO

| Persona | Role | Device | Environment | Goal | Constraint |
|---|---|---|---|---|---|
| Frank | Trader | iPhone | Telegram | Aprobar/rechazar órdenes instantáneamente | No quiere esperar 5 minutos |
| Sistema | Bot | Pi | 24/7 | No bloquear threads por aprobaciones | Callback-driven |

---

## WHAT — Constraints

- [ ] Reemplazar `request_approval()` síncrono por `ApprovalManager` asíncrono
- [ ] Usar `CallbackQueryHandler` de python-telegram-bot
- [ ] Pendientes almacenados en dict en memoria: `{symbol: (future, deadline, message_id)}`
- [ ] Timeout manejado por `asyncio.create_task(asyncio.sleep(timeout))`
- [ ] Editar mensaje original en Telegram al resolver (Aprobado / Cancelado / Timeout)
- [ ] Solo aceptar callbacks del `TELEGRAM_CHAT_ID` configurado

**Module-specific rules**:
- [ ] No modificar firma pública de `request_approval()` en `api/main.py` (o adaptar mínimamente)
- [ ] Degradación graceful: si bot no está corriendo, auto-rechazar

---

## HOW — Implementation Approach

**app/notifications/approval.py**:
```python
class ApprovalManager:
    def __init__(self, bot, chat_id): ...
    
    async def request_approval(self, symbol, action, units, ... timeout=300) -> bool:
        # Send message with InlineKeyboard
        # Store pending approval
        # Wait for callback or timeout
        # Return True/False
    
    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        # Parse callback_data: "approve_SYMBOL" or "cancel_SYMBOL"
        # Resolve future
        # Edit original message
```

**app/notifications/telegram_bot.py**:
- Agregar `CallbackQueryHandler` en `start_bot()`:
```python
app.add_handler(CallbackQueryHandler(approval_manager.handle_callback, pattern="^(approve|cancel)_"))
```

**app/api/main.py**:
- `orders_place()` usa `await approval_manager.request_approval(...)` si `REQUIRE_HUMAN_APPROVAL`

---

## Code Search

- [ ] `app/notifications/telegram.py` — `request_approval()` existente a reemplazar
- [ ] `app/notifications/telegram_bot.py` — `start_bot()` para registrar handler
- [ ] `app/api/main.py` — `orders_place()` que llama `request_approval()`
- [ ] `python-telegram-bot` docs — CallbackQueryHandler, InlineKeyboardMarkup

**Reuse decision**:
- Reuse as-is: `Bot` instance, `TELEGRAM_CHAT_ID`, `TELEGRAM_APPROVAL_TIMEOUT_SECONDS`
- Build new: `ApprovalManager`
- Remove: polling loop en `request_approval()`

---

## Reference Documents

| Document | Path | What to Extract |
|---|---|---|
| PRD | docs/dev/artifacts/notification-system/08-prd.md | REQ-04 |
| Interface design | docs/dev/artifacts/notification-system/06-interface-design.md | ApprovalManager |

---

## Acceptance Criteria

- [ ] AC-04.1: User toca "Aprobar" → orden ejecuta en < 3s
- [ ] AC-04.2: Timeout 5 min sin respuesta → future resuelve False, mensaje editado
- [ ] AC-04.3: APScheduler thread NO bloqueado durante espera
- [ ] AC-04.4: Callback de chat_id incorrecto → ignorado
- [ ] AC-04.5: Mensaje original editado a "✅ Aprobado" o "❌ Cancelado"

## Definition of Done

- [ ] Todos ACs verificados
- [ ] Tests nuevos: callback aprobación, callback cancelación, timeout
- [ ] `request_approval()` antiguo eliminado
- [ ] Issue movido a `done/`
