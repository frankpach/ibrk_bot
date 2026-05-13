# Constraints: notification-system

**Module**: notification-system
**Last Updated**: 2026-05-12

## Global Rules

See CLAUDE.backend.md and CLAUDE.frontend.md for complete ruleset.

## Module-Specific Constraints

- Must not break existing `notify()` callers — provide backward-compatible wrapper.
- Must work with `python-telegram-bot` v20+ (already installed).
- Must not add heavy DB writes (notification history optional, in-memory default).
- Must handle Telegram API rate limits (30 msg/sec per chat, 20 msg/min to same group).
- Must gracefully degrade if Telegram is down (log and drop, no crash).
- Must support runtime mode changes (critical_only → normal → verbose) without restart.
- Approval callbacks must not block APScheduler threads.

## Module Dependencies

| Module | Enabled | depends_on | produces_for | Relationship |
|--------|---------|------------|--------------|--------------|
| dev-plan | ✅ | — | notification-system | Consumers of throttled notifications |
| notification-system | ✅ | dev-plan (settings, bot) | dev-plan | Provides notification infrastructure |
