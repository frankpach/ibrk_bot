# Interface Design: notification-system

## Chosen Alternative

**Alternative B: User-first** — matches real workflows, mobile-aware, control del usuario sobre el ruido.

**Why**: El problema principal es la experiencia del usuario con el spam. La solución debe poner a Frank en control. Alternative A (depth-first) habría optimizado por latencia interna. Alternative C (reusability-first) habría agregado abstracciones innecesarias para un sistema de un solo usuario.

## Primary Interface

```python
# Central throttled notification entry point
class NotificationThrottler:
    def notify_if_changed(
        self,
        message_type: str,           # e.g., "circuit_breaker", "position_closed"
        content: str,                # The message to send
        content_hash: str | None = None,  # Optional hash for dedup
        force: bool = False,         # Bypass throttling
    ) -> bool: ...                  # True if sent, False if throttled

    def reset_state(self, message_type: str) -> None: ...

# Notification levels
class NotificationPolicy:
    level: Literal["critical_only", "normal", "verbose"]
    
    def should_notify(self, message_type: str) -> bool: ...

# Async-safe delivery
class NotificationQueue:
    def start(self) -> None: ...           # Start daemon thread
    def stop(self) -> None: ...            # Stop gracefully
    def enqueue(self, content: str) -> None: ...

# Approval system (async, non-blocking)
class ApprovalManager:
    def request_approval(
        self,
        symbol: str,
        action: str,
        units: int,
        entry_price: float,
        stop_loss_price: float,
        take_profit_price: float,
        estimated_risk_usd: float,
        timeout_seconds: int = 300,
    ) -> asyncio.Future[bool]: ...          # Future resolves on approval/cancel/timeout

    def handle_callback(self, callback_data: str) -> None: ...
```

## Key Workflows

### Workflow 1: Circuit Breaker Activation (Anti-Spam)

1. `controller.check_circuit_breaker()` detects loss > 5%.
2. Calls `throttler.notify_if_changed("circuit_breaker", content)`.
3. Throttler checks: "Did I send 'circuit_breaker' in the last 24h?"
4. First time: sends message. Returns True.
5. Subsequent checks (2 min later): "Already sent. Skip." Returns False.
6. When `controller.resume()` is called: `throttler.reset_state("circuit_breaker")`.
7. If circuit breaker triggers again: message sent once more.

### Workflow 2: Order Approval (Non-Blocking)

1. `api/main.py` receives order request with `REQUIRE_HUMAN_APPROVAL=True`.
2. Calls `approval_manager.request_approval(...)`.
3. ApprovalManager sends Telegram message with InlineKeyboard (Aprobar/Cancelar).
4. Returns immediately with `asyncio.Future`.
5. User taps "Aprobar" → `CallbackQueryHandler` triggers `handle_callback("approve_SYMBOL")`.
6. Future resolves to `True`. API places order.
7. If timeout: Future resolves to `False`. API rejects order.

### Workflow 3: Daily Digest (Instead of Continuous Alerts)

1. APScheduler job runs every 4 hours.
2. Collects: open positions P&L, signals processed, daily P&L, system status.
3. Calls `notify_if_changed("digest", content, force=True)` (digest always sends).
4. During digest window: individual non-critical alerts are suppressed.

## Components to Build

- `NotificationThrottler` (new)
- `NotificationQueue` (new)
- `NotificationPolicy` (new)
- `ApprovalManager` (new)
- Updated `notify()` function (backward-compatible wrapper)

## Components to Reuse/Extend

- `python-telegram-bot` Bot instance
- APScheduler for digest jobs
- Existing `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`

## Events to Publish

- None (this module is infrastructure, not business logic)

## Events to Consume

- Telegram callback queries (`callback_query` with `approve_*` / `cancel_*` data)

## Trade-offs Made

- **Optimizing for**: User experience and elimination of spam.
- **Sacrificing**: Real-time delivery latency (queue adds ~50-100ms). Granular per-event configuration.
- **Why this is the right choice**: The current system is unusable due to spam. Latency of 100ms on a Telegram notification is irrelevant.
