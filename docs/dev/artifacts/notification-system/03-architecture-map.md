# Architecture Map: notification-system

## Existing Components

The notification system currently consists of:
- `app/notifications/telegram.py`: sync `notify()` using `asyncio.run()` — has threading/concurrency bugs.
- `app/notifications/telegram_bot.py`: bidirectional Telegram bot with command handlers.
- `app/system/controller.py`: `check_circuit_breaker()` calls `notify()` on every check (every 2 min).
- `app/positions/manager.py`: `check_positions()` calls `notify()` on position close.
- `app/llm/loop.py`: `process_pending_signals()` calls `notify()` for every signal.

## Existing Events / Patterns

- No event bus exists. Notifications are direct function calls.
- APScheduler jobs trigger notification points: every 2 min (positions), every 15 min (signals), every 2 min (circuit breaker).
- `python-telegram-bot` is already installed and running in a separate thread.

## Existing Models

- No notification-specific DB tables. Notification history is lost after process restart.

## Gaps Identified

1. **No notification state memory**: Cannot answer "did I already tell the user about this?"
2. **No async-safe notification channel**: `asyncio.run()` in APScheduler threads is broken.
3. **No notification policy/levels**: All or nothing.
4. **No approval callback mechanism**: `request_approval()` does synchronous polling for 5 minutes.
5. **No digest/summary mode**: Only point-in-time alerts exist.

## New Components Needed

1. `app/notifications/throttler.py`: `NotificationThrottler` class with in-memory state + optional DB persistence.
2. `app/notifications/queue.py`: Dedicated notification thread with `queue.Queue` for async-safe delivery.
3. `app/notifications/policy.py`: `NotificationPolicy` dataclass with levels and rules.
4. `app/notifications/approval.py`: Async callback handlers using `CallbackQueryHandler` from python-telegram-bot.

## Components to Reuse

- `python-telegram-bot` Bot instance (already configured).
- `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` from settings.
- APScheduler (already running) for digest jobs.

## Anti-Patterns Detected

- **Anti-Pattern: Direct notify() from business logic**: 6+ modules call `notify()` directly. Should call `throttler.notify_if_changed()`.
- **Anti-Pattern: asyncio.run() from sync code**: `notify()` uses `asyncio.run()` which is unsafe in threads. Must use a thread-safe queue.

## Module Dependencies

| Module | Relationship |
|--------|-------------|
| `dev-plan` (system/controller) | Calls notify() — will call throttler instead |
| `dev-plan` (positions/manager) | Calls notify() on close — will call throttler instead |
| `dev-plan` (llm/loop) | Calls notify() on signal — will call throttler instead |
| `dev-plan` (api/main) | `request_approval()` lives here — will be refactored |
