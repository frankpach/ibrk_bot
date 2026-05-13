# Design Concept: notification-system

## Problem Statement

El sistema IBKR AI Trader envía notificaciones sin memoria de estado ni control de frecuencia. El usuario recibe el mismo mensaje (Circuit Breaker, desconexión IB, etc.) cientos de veces. Esto genera fatiga, desconfianza y reduce la utilidad del canal Telegram como fuente de información. Además, no hay niveles de notificación: el usuario no puede elegir entre "solo crítico" y "todo".

## Solution

Un sistema de notificaciones con:
1. **NotificationThrottler**: memoria de estado que evita re-notificar sobre condiciones ya comunicadas.
2. **Niveles de notificación**: `critical_only`, `normal`, `verbose`.
3. **Modo silencio temporal**: `/silencio 2h` para pausar notificaciones no críticas.
4. **Digest periódico**: resumen cada 4h en lugar de alertas continuas.
5. **Async queue**: thread dedicado para notificaciones, eliminando `asyncio.run()` desde sync.
6. **Approval callbacks nativos**: reemplazar polling síncrono bloqueante por `CallbackQueryHandler` de python-telegram-bot.

## Target Users

- **Frank (Trader/Operator)**: Recibe notificaciones en Telegram. Quiere saber qué pasa sin ser bombardeado.
- **Sistema Autónomo (Bot)**: Genera eventos que deben notificarse (o no) según política.

## Key Differentiators

- No más spam: una decisión comunicada una sola vez.
- Contexto rico: las notificaciones incluyen "por qué" y "qué hacer".
- Control del usuario: elige su nivel de ruido.

## Out of Scope

- Nuevas fuentes de notificación (email, SMS, push).
- Dashboard web en tiempo real (ya existe, no se modifica).
- Traducción a otros idiomas.

## Success Metrics

- Reducción de notificaciones duplicadas a 0%.
- Frank no desactiva el bot por spam.
- Tiempo de respuesta a aprobaciones < 5s (vs 5min polling actual).

## Open Questions

- ¿Guardar historial de notificaciones en DB para audit?
- ¿Qué pasa si Telegram está caído — buffer en memoria o drop?
