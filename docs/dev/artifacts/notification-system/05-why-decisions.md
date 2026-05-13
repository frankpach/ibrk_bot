# Why Decisions: notification-system

**Module**: notification-system
**Last Updated**: 2026-05-12

## Decision 1: In-memory throttling by default, not DB

**Context**: Could persist notification history to SQLite.
**Decision**: In-memory dict with `(message_type, content_hash, last_sent_at)`.
**Why**: DB writes for every notification would add latency and wear on SD card (Raspberry Pi). Notification dedup only needs to survive process lifetime — a restart resets state, which is acceptable.
**Trade-off**: If bot restarts, it might re-notify about an existing condition. Mitigation: check actual system state on startup before notifying.

## Decision 2: Dedicated notification thread instead of asyncio.run()

**Context**: `notify()` currently uses `asyncio.run()` which crashes when called from APScheduler threads.
**Decision**: Single daemon thread with `queue.Queue`. All notifications go to the queue. The thread owns the event loop and sends messages.
**Why**: Eliminates concurrency bugs. Simple to implement. Python-telegram-bot works well with this pattern.
**Trade-off**: Slightly more latency (queue + thread context switch). Acceptable for notifications.

## Decision 3: CallbackQueryHandler for approvals instead of polling loop

**Context**: `request_approval()` blocks a thread for 5 minutes doing `while time < deadline: check_updates()`.
**Decision**: Use `CallbackQueryHandler` registered in the bot application. Store pending approvals in a dict. Timeout handled by APScheduler or asyncio task.
**Why**: Native Telegram bot pattern. Non-blocking. User gets instant feedback. No wasted CPU.
**Trade-off**: Requires restructuring the approval flow to be event-driven instead of synchronous return-value.

## Decision 4: Three notification levels, not configurable per-event-type

**Context**: Could allow per-event-type configuration (e.g., "notify me about positions but not about scans").
**Decision**: Three global levels: `critical_only`, `normal`, `verbose`.
**Why**: Per-event config is too complex for a single-user system. Three levels capture 95% of use cases with zero config UI complexity.
**Trade-off**: Less granular control. If needed later, can extend without breaking.

## Decision 5: No notification history table (for now)

**Context**: Could create a `notifications` table to audit what was sent.
**Decision**: Skip. Use logs if audit needed.
**Why**: Single user, low compliance need. Adding a table adds migration complexity.
**Trade-off**: Cannot query "what did I miss yesterday?" beyond logs.
