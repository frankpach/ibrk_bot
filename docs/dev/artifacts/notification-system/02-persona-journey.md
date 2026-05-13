# Persona Journey: notification-system

## Persona 1: Frank (Trader / Operator)

**Goal**: Supervisar el sistema sin ser bombardeado. Tomar decisiones rápidas cuando se requiera.

**Journey: Circuit Breaker se activa**

1. **Evento**: Pérdida diaria supera 5%. Sistema se pausa.
2. **Notificación única**: "CIRCUIT BREAKER ACTIVADO. Pérdida: -$48 (9.7%). Sistema pausado. /reanudar para continuar. /diagnostico para revisar."
3. **Silencio**: El sistema NO vuelve a notificar sobre el mismo circuit breaker.
4. **Frank reanuda**: Usa /reanudar cuando está listo.
5. **Confirmación**: "Sistema reanudado. Circuit breaker reseteado."

**Journey: Aprobación de orden en modo live**

1. **Evento**: LLM decide BUY NVDA.
2. **Notificación con botones**: Precio, SL, TP, riesgo. Botones "Aprobar" / "Cancelar".
3. **Frank toca Aprobar**: Orden se ejecuta en < 3 segundos.
4. **Confirmación**: "NVDA comprada @ $214.91. Order ID: ..."
5. **Si timeout**: "Orden NVDA cancelada (timeout)."

**Journey: Pérdida de conexión IB**

1. **Evento**: IB Gateway se desconecta.
2. **Notificación única**: "⚠️ IB Gateway desconectado. Reintentando..."
3. **Reconexión**: "IB Gateway reconectado después de 45s."
4. **Si > 15 min**: "IB desconectado hace 15 min. Revisar /diagnostico." (una sola vez)

**Pain Points**
- Antes: 1000 mensajes idénticos del circuit breaker.
- Antes: Polling bloqueante de 5 min para aprobaciones.
- Antes: No puede silenciar el bot temporalmente.

## Persona 2: Sistema Autónomo (Bot)

**Goal**: Generar eventos relevantes y notificar según política sin intervención humana.

**Journey: Señal detectada → Decisión → Notificación (o silencio)**

1. Scanner detecta señal STRONG en AAPL.
2. LLM analiza y decide IGNORE.
3. Política `normal`: notifica "LLM ignora AAPL: [justificación]".
4. Política `critical_only`: no notifica (no es crítico).

**Pain Points**
- Antes: `asyncio.run()` crashea desde threads APScheduler.
- Antes: No sabe si ya notificó algo — envía de nuevo.

## Device & Environment

- **Frank**: iPhone, Telegram app, conexión móvil intermitente.
- **Bot**: Raspberry Pi, Python 3.13, APScheduler threads.

## Critical Flows

1. `circuit_breaker_activated` → notify_once → silencio hasta reset.
2. `order_approval_request` → async callback → execute or cancel.
3. `ib_disconnected` → notify_once → notify_on_reconnect.
4. `position_closed` → notify_once with post-mortem summary.
5. `daily_digest` → scheduled summary → no individual alerts during digest window.
