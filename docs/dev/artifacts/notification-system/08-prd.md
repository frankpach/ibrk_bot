# PRD: notification-system

## Overview

Replace the broken notification infrastructure of IBKR AI Trader with a spam-free, user-controllable, async-safe system.

## Requirements

### REQ-01: NotificationThrottler

- Must track last sent message per `(message_type, content_hash)`.
- Must enforce minimum interval per message type:
  - `circuit_breaker`: once per activation (reset on resume)
  - `position_closed`: once per trade_id
  - `position_opened`: once per trade_id
  - `ib_disconnected`: once per disconnection event
  - `ib_reconnected`: only if previously disconnected
  - `signal_ignored`: never (unless verbose mode)
  - `scan_failed`: once per scan type per day
  - `digest`: always sends (no throttle)
- Must support `force=True` to bypass throttle.
- Must provide `reset_state(message_type)` for external state changes.

**AC-01.1**: Two `notify_if_changed("circuit_breaker", ...)` calls in a row → only first sends.
**AC-01.2**: After `reset_state("circuit_breaker")`, next call sends again.
**AC-01.3**: `notify_if_changed("position_closed", ..., content_hash="trade_42")` → sent once.

### REQ-02: NotificationQueue (Async-Safe)

- Dedicated daemon thread with `queue.Queue`.
- All notifications go through the queue.
- The thread owns the asyncio event loop for python-telegram-bot.
- Graceful shutdown on system stop.
- If Telegram API fails, retry once after 5s, then log and drop.

**AC-02.1**: `notify()` called from APScheduler thread → no exception, message delivered.
**AC-02.2**: 100 notifications enqueued in 1 second → all delivered within 5 seconds (rate limit handling).
**AC-02.3**: Telegram API down → no crash, message logged as failed.

### REQ-03: NotificationPolicy (Levels)

Three levels:
- `critical_only`: circuit_breaker, position_closed, fatal_errors, approval_requests
- `normal`: critical + position_opened, ib_disconnected/reconnected, daily_digest
- `verbose`: everything (signals, scans, analysis progress)

- Must be set via `settings.NOTIFICATION_LEVEL` (default: `normal`).
- Runtime override via `/notificaciones critico|normal|verbose` command in Telegram.

**AC-03.1**: Level `critical_only` → `signal_ignored` is NOT sent.
**AC-03.2**: Level `verbose` → `signal_ignored` IS sent.
**AC-03.3**: `/notificaciones critico` changes level at runtime without restart.

### REQ-04: ApprovalManager (Non-Blocking)

- Replace synchronous `request_approval()` polling loop.
- Use `CallbackQueryHandler` for "Aprobar" / "Cancelar" buttons.
- Store pending approvals in memory dict: `{symbol: (future, deadline)}`.
- Auto-timeout via `asyncio.create_task` with `asyncio.sleep(timeout)`.
- If approved: resolve future to True, edit Telegram message to "✅ Aprobado".
- If cancelled/timeout: resolve future to False, edit message to "❌ Cancelado / Timeout".

**AC-04.1**: User taps "Aprobar" → order executes within 3 seconds.
**AC-04.2**: No response in 5 minutes → future resolves False, message updated.
**AC-04.3**: APScheduler thread is NOT blocked during approval wait.

### REQ-05: Daily Digest

- Scheduled every 4 hours during market hours (10:00, 14:00 ET).
- Content:
  ```
  📊 Resumen 14:00 ET
  Posiciones abiertas: 2 (NVDA +1.2%, AAPL -0.5%)
  P&L día: -$12 (no alarma)
  Señales procesadas: 3
  Estado: Normal
  ```
- Suppresses non-critical individual alerts during the 5-minute digest window.

**AC-05.1**: Digest sends at scheduled time.
**AC-05.2**: During digest window, `position_opened` alert is queued, not sent immediately.

### REQ-06: Backward Compatibility

- Existing `notify(message)` calls must continue working.
- `notify()` becomes a thin wrapper: `throttler.notify_if_changed("generic", message, force=True)`.
- Existing `request_approval()` signature preserved for `api/main.py`.

**AC-06.1**: Zero changes required in `controller.py`, `positions/manager.py`, `llm/loop.py`.
**AC-06.2**: All existing tests pass without modification.

## Performance

- Notification delivery latency: < 500ms (queue + Telegram API).
- Approval response latency: < 3s (callback-driven).
- Memory: throttler state < 1KB (small dict).

## Security

- Approval callbacks only accepted from `TELEGRAM_CHAT_ID`.
- No sensitive data in Telegram messages (order IDs, account numbers).

## Open Questions

- Should notification history be persisted to DB? (Deferred to future release.)
- Should failed notifications be retried with exponential backoff? (No — log and drop.)
