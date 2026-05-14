# Constraints: arch-refactor

**Module**: arch-refactor
**Last Updated**: 2026-05-14

## Global Rules (este proyecto)

- Sistema debe permanecer operativo durante cada fase — sin downtime de trading
- Rollback documentado y ejecutable antes de iniciar cada fase
- Paper mode como red de seguridad durante fases de cambio en rutas críticas
- No SQLAlchemy/SQLModel — SQL plano + repositorios
- No microservicios — proceso único con boundaries claros
- No event sourcing — CQRS ligero (read models) es suficiente

## Reglas de Modularidad (arch-refactor)

- Archivos ≤ 300 líneas objetivo; > 400 líneas requiere split justificado
- Un archivo = una responsabilidad
- domain/ y application/ no importan infrastructure/
- Routes no contienen if/else de negocio
- No notify() desde domain/application — usar eventos
- No queries SQL fuera de infrastructure/db/

## Module-Specific Constraints

- SQLite permanece en producción hasta Fase 7
- `ibkr/client.py` puede mantenerse como singleton (protocolo IB lo requiere)
- `notifications/telegram_bot.py` puede seguir usando httpx a la API local (boundary correcto)
- Feature flags temporales permitidos para rollback en Fases 1–2

## Archivos de mayor riesgo (no tocar sin tests cubriendo)

- `app/llm/loop.py` — ruta crítica de trading
- `app/positions/manager.py` — ruta crítica de posiciones
- `app/ibkr/client.py` — conexión IB Gateway
- `app/risk/validator.py` — validación de órdenes

## Module Dependencies

- Afecta: todos los módulos de app/ (refactor transversal)
- No afecta: tests/ (no cambiar contratos de test sin migrar tests primero)
