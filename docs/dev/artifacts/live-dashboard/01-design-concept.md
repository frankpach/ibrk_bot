# Design Concept: live-dashboard

**Status**: ✓ Complete
**Date**: 2026-05-13
**Module**: live-dashboard

## Problem Statement

The current dashboard at `/dashboard` reads from local SQLite only — no live IBKR data, no floating P&L, no market discovery. When the user opens the IBKR mobile/web app, IB Gateway disconnects (single session constraint). The dashboard must show real IBKR data when available and degrade gracefully to cached data when offline.

## Solution

Architecture: **Jobs write, dashboard reads.** Existing APScheduler jobs fetch IBKR data and persist to new SQLite tables. `/dashboard/data` only does SELECT queries — zero IBKR calls from the endpoint.

Full spec: `docs/superpowers/specs/2026-05-13-live-dashboard-design.md`

## Key Decisions

- Smart refresh: 15s with open positions, 60s idle
- IB Gateway status bar always visible
- Telegram confirmation for critical actions (close position, pause scanner)
- Dark/light mode toggle
- News default tab: "Mi universo" (active symbols)
- Market Trends: 6 tabs including sector performance and implied move
- Mi Universo table: backtest calibration status, win rate, profit factor per symbol

## Success Criteria

764/764 existing tests still pass. Dashboard shows live P&L, equity curve, news, scanner, and symbol training data.
