# Persona Journey: live-dashboard

**Module**: live-dashboard
**Phase**: Phase 0 — Discovery
**Date**: 2026-05-13

## Persona: Frank — Trader/Operador

**Device**: Mobile (Tailscale) + Desktop
**Frequency**: Multiple times per day during market hours
**Context**: Frank monitors the bot remotely. Opens the dashboard to check positions, discover new symbols, and take action without going to Telegram for every task.

### Critical Flows

1. **Morning check**: Open dashboard → see overnight positions, read news for my universe, check market trends for new opportunities → add promising symbol with "+ añadir"
2. **Position management**: See floating P&L + R/R gauge → decide to close manually → click "Cerrar" → confirm in Telegram
3. **Weekly review**: Check Mi Universo table → see which symbols are calibrated vs using defaults → click "Recalibrar" on uncalibrated ones
4. **IB offline scenario**: Opens IBKR mobile app → IB Gateway goes offline → dashboard shows red status bar + cached data with timestamps → returns to bot session → reconnects

### Success State

Frank opens the dashboard on his phone, sees live P&L on open positions, checks news filtered to his 40 symbols, spots a Top Mover, adds it with one tap, and closes a losing position — all without opening Telegram.

### Failure State

Dashboard shows blank/error when IB Gateway is offline because mobile app was opened.
