# Constraints: refactor

**Module**: refactor
**Last Updated**: 2026-05-14

## Global Rules

Ver CLAUDE.md para el ruleset global completo.

## Module-Specific Constraints

- Sistema en producción activo: Raspberry Pi + IB Gateway
- Acceso via Tailscale (no exposición pública)
- Proceso único hoy; diseñar sin bloquear workers futuros
- Migración incremental: ninguna fase rompe producción
- SQLite hoy → PostgreSQL futuro (dentro del roadmap)

## Module Dependencies

- APScheduler (jobs scheduler)
- ib_insync (IBKR connection)
- FastAPI + uvicorn
- python-telegram-bot
- OpenCode (subprocess, local binary)
- SQLite (actualmente)
