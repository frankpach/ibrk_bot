# IBKR AI Trader — Completion Plan (Phases 5-7)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Completar el sistema conectando el loop señal→LLM→orden, post-mortem de aprendizaje, Telegram bot para live trading, y systemd para arranque automático.

**Architecture:** app/llm/loop.py orquesta el ciclo completo; app/llm/postmortem.py extrae patrones tras cada cierre; app/notifications/telegram.py notifica y espera aprobación; systemd lanza IB Gateway, FastAPI y scanner como servicios del sistema.

**Tech Stack:** Python 3.13, python-telegram-bot 20.7, APScheduler, httpx, systemd, OpenAI SDK (Kimi K2)

---

## Mapa de Archivos

```
~/ibkr-bot/
├── app/
│   ├── llm/
│   │   ├── agent.py           ya existe — analyze_signal()
│   │   ├── loop.py            CREAR — procesa señales pendientes → LLM → orden
│   │   └── postmortem.py      CREAR — análisis post-cierre, extrae patrones
│   ├── notifications/
│   │   ├── __init__.py        CREAR
│   │   └── telegram.py        CREAR — bot Telegram notificaciones + aprobación
│   ├── positions/
│   │   └── manager.py         MODIFICAR — llamar postmortem al cerrar trade
│   └── api/
│       └── main.py            MODIFICAR — /symbols/propose guarda en DB
├── run.py                     MODIFICAR — agregar loop.py al scheduler
├── tests/
│   ├── test_signal_loop.py    CREAR
│   └── test_postmortem.py     CREAR
└── systemd/
    ├── ibkr-api.service       CREAR
    └── ibkr-gateway.service   CREAR
```

---

## Task 1: Signal Processing Loop (señal → LLM → orden)

**Files:**
- Create: `~/ibkr-bot/app/llm/loop.py`
- Modify: `~/ibkr-bot/run.py`
- Create: `~/ibkr-bot/tests/test_signal_loop.py`

Este módulo lee señales pendientes de la DB, llama al LLM para cada una, y si decide BUY/SELL llama a /orders/place via HTTP. Es la pieza que conecta todo el sistema.

- [ ] **Step 1: Escribir tests primero**

```python
# tests/test_signal_loop.py
from unittest.mock import patch, MagicMock
from datetime import datetime
from zoneinfo import ZoneInfo
from app.db.models import Signal


def make_signal(symbol="AAPL", strength="STRONG", signal_id=1):
    return Signal(
        id=signal_id, symbol=symbol, strength=strength,
        rsi=28.5, macd=-0.12, volume_ratio=1.8,
        extra_indicators="{}", created_at=datetime.now(ZoneInfo("America/New_York")),
        processed=False,
    )


@patch("app.llm.loop.mark_signal_processed")
@patch("app.llm.loop.analyze_signal")
@patch("app.llm.loop.get_pending_signals")
def test_ignores_signal_when_llm_returns_ignore(mock_signals, mock_analyze, mock_mark):
    from app.llm.agent import LLMDecision
    mock_signals.return_value = [make_signal()]
    mock_analyze.return_value = LLMDecision("IGNORE", 0, 0, "no signal", "LOW")
    from app.llm.loop import process_pending_signals
    process_pending_signals()
    mock_mark.assert_called_once_with(1)


@patch("app.llm.loop.httpx")
@patch("app.llm.loop.mark_signal_processed")
@patch("app.llm.loop.analyze_signal")
@patch("app.llm.loop.get_pending_signals")
def test_places_order_when_llm_returns_buy(mock_signals, mock_analyze, mock_mark, mock_httpx):
    from app.llm.agent import LLMDecision
    mock_signals.return_value = [make_signal()]
    mock_analyze.return_value = LLMDecision("BUY", 0.025, 0.06, "strong signal", "HIGH")
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"status": "placed", "order_id": "42"}
    mock_httpx.post.return_value = mock_response
    from app.llm.loop import process_pending_signals
    process_pending_signals()
    mock_httpx.post.assert_called_once()
    call_args = mock_httpx.post.call_args
    assert "orders/place" in call_args[0][0]
    assert call_args[1]["json"]["symbol"] == "AAPL"
    mock_mark.assert_called_once_with(1)


@patch("app.llm.loop.mark_signal_processed")
@patch("app.llm.loop.analyze_signal")
@patch("app.llm.loop.get_pending_signals")
def test_processes_all_pending_signals(mock_signals, mock_analyze, mock_mark):
    from app.llm.agent import LLMDecision
    mock_signals.return_value = [make_signal("AAPL", signal_id=1), make_signal("MSFT", signal_id=2)]
    mock_analyze.return_value = LLMDecision("IGNORE", 0, 0, "no", "LOW")
    from app.llm.loop import process_pending_signals
    process_pending_signals()
    assert mock_mark.call_count == 2


@patch("app.llm.loop.mark_signal_processed")
@patch("app.llm.loop.analyze_signal")
@patch("app.llm.loop.get_pending_signals")
def test_marks_signal_processed_even_on_llm_error(mock_signals, mock_analyze, mock_mark):
    mock_signals.return_value = [make_signal()]
    mock_analyze.side_effect = Exception("LLM timeout")
    from app.llm.loop import process_pending_signals
    process_pending_signals()
    mock_mark.assert_called_once_with(1)
```

- [ ] **Step 2: Correr tests — verificar que fallan**

```bash
ssh aiutox-pi "cd ~/ibkr-bot && source .venv/bin/activate && pytest tests/test_signal_loop.py -v 2>&1 | tail -10"
```
Esperado: `ModuleNotFoundError: No module named 'app.llm.loop'`

- [ ] **Step 3: Crear app/llm/loop.py**

```python
# app/llm/loop.py
"""
Procesa señales técnicas pendientes pasándolas por el LLM y ejecutando órdenes.
Corre cada 15 min via APScheduler en run.py.
"""
import logging

import httpx

from app.db.database import get_pending_signals, mark_signal_processed
from app.llm.agent import LLMDecision, analyze_signal

logger = logging.getLogger(__name__)

API_BASE = "http://127.0.0.1:8088"


def process_pending_signals():
    """Lee señales STRONG/MEDIUM pendientes y ejecuta el ciclo LLM → orden."""
    signals = get_pending_signals()
    if not signals:
        logger.debug("No pending signals to process")
        return

    logger.info(f"Processing {len(signals)} pending signal(s)")

    for signal in signals:
        try:
            decision = analyze_signal(
                symbol=signal.symbol,
                strength=signal.strength,
                rsi=signal.rsi,
                macd=signal.macd,
                volume_ratio=signal.volume_ratio,
                signal_id=signal.id,
            )

            if decision.action in ("BUY", "SELL"):
                _execute_order(signal.symbol, decision)
            else:
                logger.info(f"LLM ignored signal for {signal.symbol}: {decision.justification}")

        except Exception as e:
            logger.error(f"Error processing signal {signal.id} for {signal.symbol}: {e}")
        finally:
            mark_signal_processed(signal.id)


def _execute_order(symbol: str, decision: LLMDecision):
    """Envía la orden a FastAPI — el risk validator siempre se aplica ahí."""
    payload = {
        "symbol": symbol,
        "action": decision.action,
        "quantity": 1,
        "order_type": "MKT",
        "stop_loss_pct": decision.stop_loss_pct,
        "take_profit_pct": decision.take_profit_pct,
    }
    try:
        r = httpx.post(f"{API_BASE}/orders/place", json=payload, timeout=30)
        if r.status_code == 403:
            logger.warning(f"Order rejected by risk validator for {symbol}: {r.json()}")
        elif r.status_code == 200:
            result = r.json()
            logger.info(f"Order placed: {symbol} {decision.action} — {result}")
        else:
            logger.error(f"Unexpected status {r.status_code} for {symbol}: {r.text}")
    except Exception as e:
        logger.error(f"Failed to place order for {symbol}: {e}")
```

- [ ] **Step 4: Correr tests**

```bash
ssh aiutox-pi "cd ~/ibkr-bot && source .venv/bin/activate && pytest tests/test_signal_loop.py -v 2>&1"
```
Esperado: 4 tests PASS

- [ ] **Step 5: Agregar process_pending_signals al scheduler en run.py**

Leer run.py actual y modificar la función `main()` para agregar el job del loop después del scanner:

```python
# Agregar este import al inicio de run.py:
from app.llm.loop import process_pending_signals

# Agregar este job en el scheduler dentro de main(), después del scanner job:
scheduler.add_job(
    process_pending_signals,
    "interval",
    minutes=SCAN_INTERVAL_MINUTES,
    id="signal_processor",
)
```

- [ ] **Step 6: Reiniciar y verificar**

```bash
ssh aiutox-pi "kill \$(ps aux | grep 'run.py' | grep -v grep | awk '{print \$2}') 2>/dev/null; sleep 2"
ssh aiutox-pi "cd ~/ibkr-bot && source .venv/bin/activate && nohup python3 run.py > /tmp/run.log 2>&1 & sleep 8 && curl -s http://127.0.0.1:8088/health"
ssh aiutox-pi "tail -5 /tmp/run.log"
```
Esperado: health OK, log muestra "signal_processor" en el scheduler.

- [ ] **Step 7: Commit**

```bash
ssh aiutox-pi "cd ~/ibkr-bot && git add app/llm/loop.py tests/test_signal_loop.py run.py && git commit -m 'feat: connect signal→LLM→order loop'"
```

---

## Task 2: Post-mortem y extracción de patrones

**Files:**
- Create: `~/ibkr-bot/app/llm/postmortem.py`
- Modify: `~/ibkr-bot/app/positions/manager.py`
- Create: `~/ibkr-bot/tests/test_postmortem.py`

Cuando el position manager cierra un trade, llama al LLM para analizar si la decisión fue buena y extrae un patrón explícito que se guarda en la tabla `patterns`.

- [ ] **Step 1: Escribir tests**

```python
# tests/test_postmortem.py
from unittest.mock import patch, MagicMock
from datetime import datetime
from zoneinfo import ZoneInfo
from app.db.models import Trade


def make_closed_trade(pnl_pct=0.04, exit_reason="TAKE_PROFIT"):
    return Trade(
        id=1, symbol="AAPL", action="BUY", quantity=3,
        entry_price=280.0, stop_loss_price=273.0, take_profit_price=296.8,
        stop_loss_pct=0.025, take_profit_pct=0.06,
        signal_strength="STRONG", llm_justification="RSI oversold + MACD crossover",
        status="CLOSED", exit_price=280.0 * (1 + pnl_pct),
        exit_reason=exit_reason, pnl_usd=round(280.0 * pnl_pct * 3, 2),
        pnl_pct=pnl_pct,
        opened_at=datetime(2026, 5, 5, 10, 0, tzinfo=ZoneInfo("America/New_York")),
        closed_at=datetime(2026, 5, 6, 14, 0, tzinfo=ZoneInfo("America/New_York")),
        order_id="42",
    )


@patch("app.llm.postmortem.insert_pattern")
@patch("app.llm.postmortem.OpenAI")
def test_inserts_pattern_after_win(mock_openai_cls, mock_insert):
    mock_llm = MagicMock()
    mock_openai_cls.return_value = mock_llm
    mock_response = MagicMock()
    mock_response.choices[0].message.content = "AAPL + RSI<30 + MACD alcista → BUY confiable"
    mock_llm.chat.completions.create.return_value = mock_response

    from app.config.settings import LLM_API_KEY
    import app.llm.postmortem as pm
    original_key = pm.LLM_API_KEY

    import app.llm.postmortem
    app.llm.postmortem.LLM_API_KEY = "test-key"

    from app.llm.postmortem import run_postmortem
    run_postmortem(make_closed_trade(pnl_pct=0.04, exit_reason="TAKE_PROFIT"))

    mock_insert.assert_called_once()
    call_args = mock_insert.call_args[0][0]
    assert call_args.symbol == "AAPL"
    assert call_args.win_count == 1
    assert call_args.loss_count == 0

    app.llm.postmortem.LLM_API_KEY = original_key


@patch("app.llm.postmortem.insert_pattern")
@patch("app.llm.postmortem.OpenAI")
def test_inserts_loss_pattern_after_stop_loss(mock_openai_cls, mock_insert):
    mock_llm = MagicMock()
    mock_openai_cls.return_value = mock_llm
    mock_response = MagicMock()
    mock_response.choices[0].message.content = "AAPL + RSI marginal → evitar entrada sin volumen"
    mock_llm.chat.completions.create.return_value = mock_response

    import app.llm.postmortem
    app.llm.postmortem.LLM_API_KEY = "test-key"

    from app.llm.postmortem import run_postmortem
    run_postmortem(make_closed_trade(pnl_pct=-0.025, exit_reason="STOP_LOSS"))

    mock_insert.assert_called_once()
    call_args = mock_insert.call_args[0][0]
    assert call_args.win_count == 0
    assert call_args.loss_count == 1


@patch("app.llm.postmortem.insert_pattern")
def test_skips_postmortem_without_api_key(mock_insert):
    import app.llm.postmortem
    app.llm.postmortem.LLM_API_KEY = ""
    from app.llm.postmortem import run_postmortem
    run_postmortem(make_closed_trade())
    mock_insert.assert_not_called()
```

- [ ] **Step 2: Correr tests — verificar que fallan**

```bash
ssh aiutox-pi "cd ~/ibkr-bot && source .venv/bin/activate && pytest tests/test_postmortem.py -v 2>&1 | tail -10"
```
Esperado: `ModuleNotFoundError: No module named 'app.llm.postmortem'`

- [ ] **Step 3: Crear app/llm/postmortem.py**

```python
# app/llm/postmortem.py
"""
Análisis post-mortem de trades cerrados.
Llama al LLM para extraer un patrón aprendido y lo guarda en DB.
"""
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from openai import OpenAI

from app.config.settings import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL, MARKET_TZ
from app.db.database import insert_pattern
from app.db.models import Pattern, Trade

logger = logging.getLogger(__name__)


def run_postmortem(trade: Trade):
    """Analiza un trade cerrado y extrae un patrón aprendido."""
    if not LLM_API_KEY:
        logger.debug("LLM_API_KEY not set — skipping postmortem")
        return

    outcome = "GANANCIA" if (trade.pnl_pct or 0) >= 0 else "PÉRDIDA"
    prompt = f"""Analiza esta operación de trading cerrada y extrae UN patrón aprendido conciso.

Símbolo: {trade.symbol}
Acción: {trade.action}
Señal: {trade.signal_strength}
Justificación original: {trade.llm_justification}
Entrada: ${trade.entry_price:.2f}
Stop-loss: ${trade.stop_loss_price:.2f} ({trade.stop_loss_pct:.1%})
Take-profit: ${trade.take_profit_price:.2f} ({trade.take_profit_pct:.1%})
Resultado: {outcome}
PnL: {trade.pnl_pct:.2%} (${trade.pnl_usd:.2f})
Razón de cierre: {trade.exit_reason}

Responde SOLO con una frase corta que describa el patrón aprendido.
Ejemplos: "AAPL + RSI<30 + MACD alcista → BUY confiable en apertura"
          "TSLA + volumen bajo + señal MEDIUM → evitar, demasiado ruido"
"""

    try:
        llm = OpenAI(api_key=LLM_API_KEY, base_url=LLM_BASE_URL)
        response = llm.chat.completions.create(
            model=LLM_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=100,
        )
        pattern_text = response.choices[0].message.content.strip()

        is_win = (trade.pnl_pct or 0) >= 0
        now = datetime.now(tz=MARKET_TZ)

        insert_pattern(Pattern(
            id=None,
            symbol=trade.symbol,
            pattern_text=pattern_text,
            win_count=1 if is_win else 0,
            loss_count=0 if is_win else 1,
            created_at=now,
            updated_at=now,
        ))

        logger.info(f"Postmortem pattern saved for {trade.symbol}: {pattern_text}")

    except Exception as e:
        logger.error(f"Postmortem failed for trade {trade.id}: {e}")
```

- [ ] **Step 4: Correr tests**

```bash
ssh aiutox-pi "cd ~/ibkr-bot && source .venv/bin/activate && pytest tests/test_postmortem.py -v 2>&1"
```
Esperado: 3 tests PASS

- [ ] **Step 5: Modificar position manager para llamar postmortem**

Leer el archivo actual:
```bash
ssh aiutox-pi "cat ~/ibkr-bot/app/positions/manager.py"
```

Agregar el import al inicio y llamar postmortem después de `close_trade`:

```python
# Al inicio de manager.py, agregar:
from app.llm.postmortem import run_postmortem

# Dentro de check_positions(), reemplazar el bloque if exit_reason: con:
        if exit_reason:
            logger.info(f"Closing trade {trade.id} {trade.symbol} reason={exit_reason} pnl={pnl_pct:.2%} ${pnl_usd:.2f}")
            close_trade(
                trade_id=trade.id, exit_price=price, exit_reason=exit_reason,
                pnl_usd=round(pnl_usd, 2), pnl_pct=round(pnl_pct, 4),
            )
            # Actualizar trade con datos de cierre para el postmortem
            trade.exit_price = price
            trade.exit_reason = exit_reason
            trade.pnl_usd = round(pnl_usd, 2)
            trade.pnl_pct = round(pnl_pct, 4)
            try:
                run_postmortem(trade)
            except Exception as e:
                logger.error(f"Postmortem error for trade {trade.id}: {e}")
```

- [ ] **Step 6: Correr todos los tests**

```bash
ssh aiutox-pi "cd ~/ibkr-bot && source .venv/bin/activate && pytest tests/test_signal_loop.py tests/test_postmortem.py tests/test_risk_validator.py tests/test_preprocessor.py -v 2>&1 | tail -15"
```
Esperado: mínimo 14 PASS (4+3+7+6 — test_ibkr_client excluido por necesitar IB Gateway)

- [ ] **Step 7: Commit**

```bash
ssh aiutox-pi "cd ~/ibkr-bot && git add app/llm/postmortem.py app/positions/manager.py tests/test_postmortem.py && git commit -m 'feat: add postmortem pattern extraction after trade close'"
```

---

## Task 3: Telegram Bot (notificaciones + aprobación live)

**Files:**
- Create: `~/ibkr-bot/app/notifications/__init__.py`
- Create: `~/ibkr-bot/app/notifications/telegram.py`
- Modify: `~/ibkr-bot/app/api/main.py` — usar telegram en /orders/place cuando REQUIRE_HUMAN_APPROVAL=True

- [ ] **Step 1: Instalar python-telegram-bot**

```bash
ssh aiutox-pi "cd ~/ibkr-bot && source .venv/bin/activate && pip install 'python-telegram-bot==20.7' && python3 -c 'import telegram; print(telegram.__version__)'"
```
Esperado: `20.7`

- [ ] **Step 2: Crear directorios**

```bash
ssh aiutox-pi "mkdir -p ~/ibkr-bot/app/notifications && touch ~/ibkr-bot/app/notifications/__init__.py"
```

- [ ] **Step 3: Crear app/notifications/telegram.py**

```python
# app/notifications/telegram.py
"""
Telegram bot para notificaciones de trading y aprobación humana de órdenes live.

Paper mode: notifica sin esperar respuesta.
Live mode: envía botones Aprobar/Cancelar, espera TELEGRAM_APPROVAL_TIMEOUT_SECONDS.
           Si no hay respuesta → cancela automáticamente.
"""
import logging
import threading
import time

from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import TelegramError

from app.config.settings import (
    TELEGRAM_BOT_TOKEN,
    TELEGRAM_CHAT_ID,
    TELEGRAM_APPROVAL_TIMEOUT_SECONDS,
)

logger = logging.getLogger(__name__)


def _get_bot() -> Bot | None:
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logger.warning("Telegram not configured — TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID missing")
        return None
    return Bot(token=TELEGRAM_BOT_TOKEN)


def notify(message: str) -> bool:
    """Envía notificación simple sin esperar respuesta. Retorna True si enviado."""
    bot = _get_bot()
    if not bot:
        return False
    try:
        import asyncio
        asyncio.run(bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message, parse_mode="HTML"))
        logger.info(f"Telegram notification sent: {message[:80]}")
        return True
    except TelegramError as e:
        logger.error(f"Telegram notify failed: {e}")
        return False


def request_approval(
    symbol: str,
    action: str,
    units: int,
    entry_price: float,
    stop_loss_price: float,
    take_profit_price: float,
    estimated_risk_usd: float,
) -> bool:
    """
    Envía mensaje con botones Aprobar/Cancelar y espera respuesta.
    Retorna True si aprobado, False si cancelado o timeout.
    Bloquea el hilo llamante hasta respuesta o timeout.
    """
    bot = _get_bot()
    if not bot:
        logger.warning("Telegram not configured — auto-rejecting order")
        return False

    approved_event = threading.Event()
    result = {"approved": False}

    message = (
        f"🔔 <b>Nueva orden pendiente de aprobación</b>\n\n"
        f"Símbolo: <b>{symbol}</b>\n"
        f"Acción: <b>{action}</b>\n"
        f"Unidades: <b>{units}</b>\n"
        f"Precio entrada: <b>${entry_price:.2f}</b>\n"
        f"Stop-loss: <b>${stop_loss_price:.2f}</b>\n"
        f"Take-profit: <b>${take_profit_price:.2f}</b>\n"
        f"Riesgo estimado: <b>${estimated_risk_usd:.2f}</b>\n\n"
        f"⏰ Tienes {TELEGRAM_APPROVAL_TIMEOUT_SECONDS // 60} minutos para responder."
    )

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Aprobar", callback_data=f"approve_{symbol}"),
            InlineKeyboardButton("❌ Cancelar", callback_data=f"cancel_{symbol}"),
        ]
    ])

    try:
        import asyncio

        async def send_and_wait():
            msg = await bot.send_message(
                chat_id=TELEGRAM_CHAT_ID,
                text=message,
                parse_mode="HTML",
                reply_markup=keyboard,
            )
            return msg.message_id

        msg_id = asyncio.run(send_and_wait())
        logger.info(f"Approval request sent for {symbol} {action}, message_id={msg_id}")

        # Polling para respuesta
        deadline = time.time() + TELEGRAM_APPROVAL_TIMEOUT_SECONDS
        while time.time() < deadline:
            try:
                async def check_updates():
                    updates = await bot.get_updates(timeout=10, allowed_updates=["callback_query"])
                    for update in updates:
                        if update.callback_query:
                            data = update.callback_query.data
                            if data == f"approve_{symbol}":
                                result["approved"] = True
                                return True
                            elif data == f"cancel_{symbol}":
                                result["approved"] = False
                                return True
                    return False

                if asyncio.run(check_updates()):
                    break

            except Exception as e:
                logger.error(f"Telegram polling error: {e}")
                time.sleep(5)

        if result["approved"]:
            notify(f"✅ Orden <b>{action} {units} {symbol}</b> aprobada. Ejecutando...")
        else:
            notify(f"❌ Orden <b>{action} {units} {symbol}</b> cancelada (timeout o rechazo).")

        return result["approved"]

    except TelegramError as e:
        logger.error(f"Telegram approval request failed: {e}")
        return False
```

- [ ] **Step 4: Modificar /orders/place en main.py para usar Telegram en live mode**

Leer la sección `if REQUIRE_HUMAN_APPROVAL:` del endpoint orders_place en `app/api/main.py` y reemplazarla:

```python
# Reemplazar el bloque if REQUIRE_HUMAN_APPROVAL: en orders_place con:
    if REQUIRE_HUMAN_APPROVAL:
        from app.notifications.telegram import request_approval
        from app.config.settings import MAX_RISK_PCT, MIN_RISK_USD
        max_risk_usd = max(capital * MAX_RISK_PCT, MIN_RISK_USD)
        estimated_risk = units * current_price * req.stop_loss_pct
        stop_loss_price = round(current_price * (1 - req.stop_loss_pct), 2)
        take_profit_price = round(current_price * (1 + req.take_profit_pct), 2)

        approved = request_approval(
            symbol=symbol,
            action=req.action,
            units=units,
            entry_price=current_price,
            stop_loss_price=stop_loss_price,
            take_profit_price=take_profit_price,
            estimated_risk_usd=round(estimated_risk, 2),
        )
        if not approved:
            raise HTTPException(status_code=403, detail={
                "approved": False,
                "reasons": ["Order rejected or timed out waiting for human approval"],
            })
        # Si aprobado, continúa al bloque paper trading abajo
```

- [ ] **Step 5: Verificar que importa sin errores**

```bash
ssh aiutox-pi "cd ~/ibkr-bot && source .venv/bin/activate && python3 -c 'from app.notifications.telegram import notify, request_approval; print(\"OK\")'"
```
Esperado: `OK`

- [ ] **Step 6: Agregar instrucciones de configuración en .env**

```bash
ssh aiutox-pi "cat >> ~/ibkr-bot/.env << 'EOF'

# Para activar Telegram:
# 1. Crear bot con @BotFather en Telegram → obtener token
# 2. Obtener tu chat_id: enviar mensaje al bot y visitar:
#    https://api.telegram.org/bot<TOKEN>/getUpdates
# TELEGRAM_BOT_TOKEN=123456:ABC...
# TELEGRAM_CHAT_ID=987654321
EOF"
```

- [ ] **Step 7: Commit**

```bash
ssh aiutox-pi "cd ~/ibkr-bot && git add app/notifications/ app/api/main.py .env && git commit -m 'feat: add Telegram bot for live order notifications and approval'"
```

---

## Task 4: Guardar proposals en DB + endpoint /symbols/approve

**Files:**
- Modify: `~/ibkr-bot/app/api/main.py`
- Modify: `~/ibkr-bot/app/db/database.py`

- [ ] **Step 1: Agregar función save_symbol_proposal a database.py**

Agregar al final de `app/db/database.py`:

```python
def save_symbol_proposal(symbol: str, reason: str):
    """Guarda un símbolo propuesto pendiente de aprobación."""
    conn = get_connection()
    now = datetime.utcnow().isoformat()
    conn.execute(
        "INSERT OR IGNORE INTO symbol_config (symbol, approved, proposed_by, created_at) VALUES (?,0,'llm',?)",
        (symbol.upper(), now)
    )
    # Guardar razón en tabla decisions como log
    conn.execute(
        """INSERT INTO decisions
           (signal_id,symbol,llm_model,prompt_summary,response,action,stop_loss_pct,take_profit_pct,created_at)
           VALUES (?,?,?,?,?,?,?,?,?)""",
        (None, symbol.upper(), "human", f"Proposal: {reason}", reason, "PROPOSE", 0, 0, now)
    )
    conn.commit()
    conn.close()


def approve_symbol(symbol: str):
    """Aprueba un símbolo propuesto para que el scanner lo incluya."""
    conn = get_connection()
    conn.execute("UPDATE symbol_config SET approved=1 WHERE symbol=?", (symbol.upper(),))
    conn.commit()
    conn.close()


def get_pending_proposals() -> list:
    """Retorna símbolos propuestos pendientes de aprobación."""
    conn = get_connection()
    rows = conn.execute("SELECT symbol, proposed_by, created_at FROM symbol_config WHERE approved=0").fetchall()
    conn.close()
    return [{"symbol": r["symbol"], "proposed_by": r["proposed_by"], "created_at": r["created_at"]} for r in rows]
```

- [ ] **Step 2: Actualizar /symbols/propose y agregar /symbols/approve en main.py**

Reemplazar el endpoint `propose_symbol` existente y agregar dos nuevos al final de `app/api/main.py`:

```python
# Reemplazar el endpoint propose_symbol existente con:
@app.post("/symbols/propose")
def propose_symbol(req: SymbolProposalRequest):
    from app.db.database import save_symbol_proposal
    symbol = req.symbol.upper()
    save_symbol_proposal(symbol, req.reason)
    return {
        "status": "pending_approval",
        "symbol": symbol,
        "reason": req.reason,
        "message": f"Symbol {symbol} saved. Use GET /symbols/proposals to review and POST /symbols/approve to activate.",
    }


# Agregar al final del archivo:
@app.get("/symbols/proposals")
def get_proposals():
    from app.db.database import get_pending_proposals
    return get_pending_proposals()


@app.post("/symbols/approve/{symbol}")
def approve_symbol_endpoint(symbol: str):
    from app.db.database import approve_symbol, get_approved_symbols
    from app.config.settings import ALLOWED_SYMBOLS
    symbol = symbol.upper()
    approve_symbol(symbol)
    # Agregar a ALLOWED_SYMBOLS en memoria para esta sesión
    if symbol not in ALLOWED_SYMBOLS:
        ALLOWED_SYMBOLS.append(symbol)
    return {"status": "approved", "symbol": symbol, "message": f"{symbol} added to active trading universe."}
```

- [ ] **Step 3: Probar el flujo completo**

```bash
# Reiniciar server
ssh aiutox-pi "kill \$(ps aux | grep 'run.py' | grep -v grep | awk '{print \$2}') 2>/dev/null; sleep 2"
ssh aiutox-pi "cd ~/ibkr-bot && source .venv/bin/activate && nohup python3 run.py > /tmp/run.log 2>&1 & sleep 8"

# Proponer símbolo
ssh aiutox-pi "curl -s -X POST http://127.0.0.1:8088/symbols/propose -H 'Content-Type: application/json' -d '{\"symbol\":\"NFLX\",\"reason\":\"Strong momentum and high volume\"}'"

# Ver proposals
ssh aiutox-pi "curl -s http://127.0.0.1:8088/symbols/proposals"

# Aprobar
ssh aiutox-pi "curl -s -X POST http://127.0.0.1:8088/symbols/approve/NFLX"

# Verificar en allowed-symbols
ssh aiutox-pi "curl -s http://127.0.0.1:8088/allowed-symbols"
```

- [ ] **Step 4: Commit**

```bash
ssh aiutox-pi "cd ~/ibkr-bot && git add app/api/main.py app/db/database.py && git commit -m 'feat: persist symbol proposals in DB, add /symbols/proposals and /symbols/approve'"
```

---

## Task 5: systemd Services para arranque automático

**Files:**
- Create: `~/ibkr-bot/systemd/ibkr-api.service`
- Create: `~/ibkr-bot/systemd/ibkr-gateway.service`

- [ ] **Step 1: Crear directorio systemd en el proyecto**

```bash
ssh aiutox-pi "mkdir -p ~/ibkr-bot/systemd"
```

- [ ] **Step 2: Crear ibkr-api.service**

```bash
ssh aiutox-pi "cat > ~/ibkr-bot/systemd/ibkr-api.service << 'EOF'
[Unit]
Description=IBKR AI Trader API + Scheduler
After=network.target
Wants=network.target

[Service]
Type=simple
User=frankpach
WorkingDirectory=/home/frankpach/ibkr-bot
EnvironmentFile=/home/frankpach/ibkr-bot/.env
ExecStart=/home/frankpach/ibkr-bot/.venv/bin/python3 /home/frankpach/ibkr-bot/run.py
Restart=on-failure
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF"
```

- [ ] **Step 3: Crear ibkr-gateway.service**

```bash
ssh aiutox-pi "cat > ~/ibkr-bot/systemd/ibkr-gateway.service << 'EOF'
[Unit]
Description=Interactive Brokers Gateway
After=network.target
Wants=network.target

[Service]
Type=simple
User=frankpach
Environment=DISPLAY=:0
ExecStart=/home/frankpach/Jts/ibgateway/1046/ibgateway
Restart=on-failure
RestartSec=30
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF"
```

- [ ] **Step 4: Instalar los servicios**

```bash
ssh aiutox-pi "sudo cp ~/ibkr-bot/systemd/ibkr-api.service /etc/systemd/system/ && sudo cp ~/ibkr-bot/systemd/ibkr-gateway.service /etc/systemd/system/ && sudo systemctl daemon-reload"
```

- [ ] **Step 5: Habilitar ibkr-api (API + scheduler)**

```bash
ssh aiutox-pi "sudo systemctl enable ibkr-api.service && sudo systemctl status ibkr-api.service | head -10"
```

Nota: ibkr-gateway.service requiere display gráfico (DISPLAY=:0) — habilitar solo si hay monitor/VNC conectado:
```bash
# Solo si tienes monitor o VNC:
# ssh aiutox-pi "sudo systemctl enable ibkr-gateway.service"
```

- [ ] **Step 6: Probar arranque del servicio API**

Primero matar el proceso manual:
```bash
ssh aiutox-pi "kill \$(ps aux | grep 'run.py' | grep -v grep | awk '{print \$2}') 2>/dev/null; sleep 2"
```

Arrancar via systemd:
```bash
ssh aiutox-pi "sudo systemctl start ibkr-api.service && sleep 10 && curl -s http://127.0.0.1:8088/health"
```
Esperado: `{"status":"ok","connected":true}`

Verificar logs:
```bash
ssh aiutox-pi "sudo journalctl -u ibkr-api.service -n 20"
```

- [ ] **Step 7: Commit**

```bash
ssh aiutox-pi "cd ~/ibkr-bot && git add systemd/ && git commit -m 'feat: add systemd services for automatic startup'"
```

---

## Self-Review

**Cobertura:**
- ✅ Loop señal→LLM→orden: Task 1 (app/llm/loop.py + run.py)
- ✅ Post-mortem + patrones: Task 2 (app/llm/postmortem.py + manager.py)
- ✅ Telegram bot notificaciones: Task 3 (app/notifications/telegram.py)
- ✅ Telegram aprobación live: Task 3 (main.py REQUIRE_HUMAN_APPROVAL)
- ✅ Symbol proposals en DB: Task 4 (database.py + main.py)
- ✅ /symbols/approve endpoint: Task 4
- ✅ systemd ibkr-api.service: Task 5
- ✅ systemd ibkr-gateway.service: Task 5

**Consistencia de tipos:**
- `run_postmortem(trade: Trade)` — Trade tiene todos los campos necesarios ✅
- `process_pending_signals()` usa `Signal.id` para mark_signal_processed ✅
- `save_symbol_proposal(symbol, reason)` — ambos strings ✅
- `approve_symbol(symbol)` — string ✅
- Telegram `request_approval()` retorna bool ✅

**Sin placeholders:** código completo en cada step ✅
