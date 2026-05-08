# app/notifications/telegram_bot.py
"""
Telegram bot bidireccional para el IBKR AI Trader.
"""
import asyncio
import json
import logging
import subprocess
import httpx

from telegram import Update
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    ContextTypes, filters,
)

from app.config.settings import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
from app.notifications.telegram import notify

logger = logging.getLogger(__name__)

from app.config.settings import API_BASE  # noqa: F401
from app.config.settings import OPENCODE_BIN  # noqa: F401
OPENCODE_MODEL = "opencode-go/qwen3.5-plus"


def _api(method: str, path: str, **kwargs) -> dict:
    """Llamada HTTP a FastAPI local."""
    try:
        fn = getattr(httpx, method)
        r = fn(f"{API_BASE}{path}", timeout=30, **kwargs)
        return r.json()
    except Exception as e:
        return {"error": str(e)}


def _call_opencode(prompt: str) -> str:
    """Llama a OpenCode y retorna la respuesta en texto."""
    try:
        result = subprocess.run(
            [OPENCODE_BIN, "run", "--model", OPENCODE_MODEL, "--format", "json", prompt],
            capture_output=True, text=True, timeout=90,
            cwd="/home/frankpach/ibkr-bot",
        )
        text_parts = []
        for line in result.stdout.strip().splitlines():
            if not line.strip():
                continue
            try:
                event = json.loads(line)
                if event.get("type") == "text":
                    text_parts.append(event["part"]["text"])
            except json.JSONDecodeError:
                continue
        return "".join(text_parts).strip() or "Sin respuesta del LLM."
    except subprocess.TimeoutExpired:
        return "El LLM tardo demasiado. Intenta de nuevo."
    except Exception as e:
        return f"Error al llamar al LLM: {e}"


def _only_owner(func):
    """Decorator: solo responde al chat_id configurado."""
    async def wrapper(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if str(update.effective_chat.id) != str(TELEGRAM_CHAT_ID):
            return
        return await func(update, ctx)
    return wrapper


@_only_owner
async def cmd_estado(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    data = _api("get", "/system/status")
    portfolio = _api("get", "/portfolio")
    if isinstance(portfolio, list) and portfolio:
        pos_text = "\n".join(
            f"  {p['symbol']}: {p['quantity']} acc @ ${p['avg_cost']:.2f} | P&L: ${p['unrealized_pnl']:.2f}"
            for p in portfolio
        )
    else:
        pos_text = "  Sin posiciones abiertas"
    msg = (
        f"Estado del sistema\n\n"
        f"Modo: {data.get('mode', '?').upper()}\n"
        f"Pausado: {'Si' if data.get('paused') else 'No'}\n"
        f"Capital simulado: ${data.get('simulated_capital', 500)}\n"
        f"P&L hoy: ${data.get('daily_pnl_usd', 0):.2f} ({data.get('daily_pnl_pct', 0):.2f}%)\n"
        f"Posiciones: {data.get('open_positions', 0)}/3\n\n"
        f"Posiciones abiertas:\n{pos_text}"
    )
    await update.message.reply_text(msg)


@_only_owner
async def cmd_posiciones(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    trades = _api("get", "/trades")
    if not trades or not isinstance(trades, list):
        await update.message.reply_text("Sin posiciones abiertas.")
        return
    lines = []
    for t in trades:
        lines.append(
            f"{t['symbol']} {t['action']} x{t['quantity']}\n"
            f"  Entrada: ${t['entry_price']:.2f}\n"
            f"  SL: ${t['stop_loss_price']:.2f} | TP: ${t['take_profit_price']:.2f}\n"
            f"  Senal: {t['signal_strength']}"
        )
    await update.message.reply_text("Posiciones abiertas:\n\n" + "\n\n".join(lines))


@_only_owner
async def cmd_historial(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    trades = _api("get", "/trades/closed?limit=5")
    if not trades or not isinstance(trades, list):
        await update.message.reply_text("Sin historial de operaciones.")
        return
    lines = []
    for t in trades:
        pnl = t.get("pnl_usd") or 0
        emoji = "+" if pnl >= 0 else "-"
        lines.append(f"{emoji} {t['symbol']} {t['action']} | ${pnl:.2f} ({t.get('exit_reason','?')})")
    await update.message.reply_text("Ultimas operaciones:\n" + "\n".join(lines))


@_only_owner
async def cmd_senales(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    signals = _api("get", "/signals")
    if not signals or not isinstance(signals, list):
        await update.message.reply_text("Sin senales pendientes.")
        return
    lines = [f"{s['symbol']} [{s['strength']}] RSI:{s['rsi']} Vol:{s['volume_ratio']}x" for s in signals]
    await update.message.reply_text("Senales pendientes:\n" + "\n".join(lines))


@_only_owner
async def cmd_simbolos(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    data = _api("get", "/allowed-symbols")
    symbols = data.get("symbols", [])
    await update.message.reply_text("Universo activo:\n" + ", ".join(symbols))


@_only_owner
async def cmd_pausar(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    _api("post", "/system/pause")
    await update.message.reply_text("Sistema pausado. Usa /reanudar para continuar.")


@_only_owner
async def cmd_reanudar(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    _api("post", "/system/resume")
    await update.message.reply_text("Sistema reanudado.")


@_only_owner
async def cmd_stop(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Deteniendo el sistema...")
    notify("Sistema detenido por comando /stop desde Telegram.")
    import os, signal as sig
    os.kill(os.getpid(), sig.SIGTERM)


@_only_owner
async def cmd_cerrar(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    args = ctx.args
    if not args:
        await update.message.reply_text("Uso: /cerrar SYMBOL o /cerrar todo")
        return
    if args[0].lower() == "todo":
        data = _api("post", "/orders/close-all")
        closed = data.get("closed", 0)
        await update.message.reply_text(f"Cerradas {closed} posiciones.")
    else:
        symbol = args[0].upper()
        data = _api("post", f"/orders/close/{symbol}")
        if "error" in data or "detail" in data:
            detail = data.get("detail", data.get("error", "Error desconocido"))
            await update.message.reply_text(f"Error: {detail}")
        else:
            pnl = data.get("pnl_usd", 0) or 0
            await update.message.reply_text(
                f"{symbol} cerrada @ ${data.get('exit_price', 0):.2f}\n"
                f"P&L: ${pnl:.2f} ({data.get('pnl_pct', 0):.2f}%)"
            )


@_only_owner
async def cmd_modo(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    args = ctx.args
    if not args or args[0].lower() not in ("paper", "live"):
        await update.message.reply_text("Uso: /modo paper o /modo live")
        return
    mode = args[0].lower()
    if mode == "live":
        await update.message.reply_text(
            "ADVERTENCIA: Cambiar a modo LIVE ejecutara ordenes REALES.\n"
            "Confirma escribiendo: /modo live confirmar"
        )
        return
    _api("post", f"/system/mode/{mode}")
    await update.message.reply_text(f"Modo cambiado a {mode.upper()}.")


@_only_owner
async def cmd_aprobar(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await update.message.reply_text("Uso: /aprobar SYMBOL")
        return
    symbol = ctx.args[0].upper()
    data = _api("post", f"/symbols/approve/{symbol}")
    await update.message.reply_text(data.get("message", f"{symbol} aprobado."))



@_only_owner
async def cmd_alerta(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if len(ctx.args) < 2:
        await update.message.reply_text(
            "Uso: /alerta SYMBOL UMBRAL\n"
            "Ejemplo: /alerta TSLA 5%\n\n"
            "Ver alertas: /alertas\n"
            "Eliminar: /eliminar_alerta ID"
        )
        return
    symbol = ctx.args[0].upper()
    threshold_str = ctx.args[1]
    from app.alerts.manager import parse_alert_command
    alert = parse_alert_command(symbol, threshold_str)
    if alert is None:
        await update.message.reply_text(f"Formato invalido. Usa: /alerta {symbol} 5%")
        return
    from app.db.database import insert_alert
    alert_id = insert_alert(alert.symbol, alert.threshold_pct)
    await update.message.reply_text(
        f"Alerta creada (ID:{alert_id})\n"
        f"{symbol}: notifica si sube o baja mas del {alert.threshold_pct:.0%}"
    )


@_only_owner
async def cmd_alertas(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    from app.db.database import get_active_alerts
    alerts = get_active_alerts()
    if not alerts:
        await update.message.reply_text("Sin alertas activas.")
        return
    lines = [f"ID:{a.id} {a.symbol} umbral:{a.threshold_pct:.0%}" for a in alerts]
    await update.message.reply_text("Alertas activas:\n" + "\n".join(lines))


@_only_owner
async def cmd_eliminar_alerta(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await update.message.reply_text("Uso: /eliminar_alerta ID")
        return
    try:
        alert_id = int(ctx.args[0])
        from app.db.database import delete_alert
        delete_alert(alert_id)
        await update.message.reply_text(f"Alerta {alert_id} eliminada.")
    except ValueError:
        await update.message.reply_text("ID debe ser un numero.")


@_only_owner
async def cmd_diagnostico(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    from app.db.database import get_connection
    from app.config.settings import CAPITAL_CAP

    lines = ["DIAGNOSTICO DEL SISTEMA", ""]

    # Capital operativo
    acc = _api("get", "/account") or {}
    real_cap = acc.get("net_liquidation", 0)
    op_cap = min(real_cap, CAPITAL_CAP)
    lines.append(f"Capital real IB:    ${real_cap:,.2f}")
    lines.append(f"Capital operativo:  ${op_cap:,.2f} (cap=${CAPITAL_CAP:.0f})")
    lines.append("")

    conn = get_connection()
    try:
        signals_count = conn.execute("SELECT COUNT(*) FROM signals").fetchone()[0]
        trades_count = conn.execute("SELECT COUNT(*) FROM trades WHERE status='CLOSED'").fetchone()[0]
        patterns_count = conn.execute("SELECT COUNT(*) FROM patterns").fetchone()[0]

        last_signals = conn.execute(
            "SELECT symbol, strength, rsi, volume_ratio, created_at FROM signals ORDER BY created_at DESC LIMIT 3"
        ).fetchall()
        last_decisions = conn.execute(
            "SELECT symbol, action, created_at FROM decisions ORDER BY created_at DESC LIMIT 3"
        ).fetchall()
    finally:
        conn.close()

    lines.append(f"Senales totales:     {signals_count}")
    lines.append(f"Trades cerrados:     {trades_count}")
    lines.append(f"Patrones aprendidos: {patterns_count}")
    lines.append("")

    if last_signals:
        lines.append("Ultimas senales:")
        for s in last_signals:
            rsi = s["rsi"] if s["rsi"] is not None else "?"
            vol = s["volume_ratio"] if s["volume_ratio"] is not None else "?"
            lines.append(f"  {s['symbol']} [{s['strength']}] RSI:{rsi} Vol:{vol}x")
        lines.append("")

    if last_decisions:
        lines.append("Ultimas decisiones:")
        for d in last_decisions:
            lines.append(f"  {d['symbol']} -> {d['action']}")
        lines.append("")

    connected = (_api("get", "/health") or {}).get("connected", False)
    lines.append("IB Gateway: " + ("conectado" if connected else "DESCONECTADO"))

    await update.message.reply_text("\n".join(lines))

@_only_owner
async def cmd_ayuda(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Comandos disponibles:\n\n"
        "Informacion:\n"
        "  /estado - resumen del sistema\n"
        "  /diagnostico - estado completo: capital, senales, patrones\n"
        "  /posiciones - posiciones abiertas\n"
        "  /historial - ultimas 5 operaciones\n"
        "  /senales - senales pendientes\n"
        "  /simbolos - universo de trading\n\n"
        "Control:\n"
        "  /pausar - detener el scanner\n"
        "  /reanudar - reactivar el scanner\n"
        "  /cerrar SYMBOL - cerrar posicion\n"
        "  /cerrar todo - cerrar todo\n"
        "  /modo paper|live - cambiar modo\n"
        "  /aprobar SYMBOL - aprobar simbolo\n"
        "  /stop - detener el sistema\n\n"
        "Analisis con IA:\n"
        "  /analizar SYMBOL - analisis completo\n"
        "  /proponer SYMBOL razon - proponer simbolo\n"
        "  Cualquier mensaje de texto - consulta libre al LLM\n\n"
        "Alertas de precio:\n"
        "  /alerta SYMBOL UMBRAL - crear alerta (ej: /alerta TSLA 5%)\n"
        "  /alertas - ver alertas activas\n"
        "  /eliminar_alerta ID - eliminar alerta"
    )


@_only_owner
@_only_owner
async def cmd_analizar(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await update.message.reply_text("Uso: /analizar SYMBOL (ej: /analizar NFLX)")
        return
    symbol = ctx.args[0].upper()

    # Run in executor to avoid blocking event loop
    loop = asyncio.get_event_loop()

    def run_pipeline():
        from app.analysis.pipeline import AnalysisPipeline, AnalysisContext
        from app.llm.agent import get_data_layer
        from app.notifications.telegram import notify as sync_notify

        data_layer = get_data_layer()
        context = AnalysisContext(mode="on_demand")
        pipeline = AnalysisPipeline(symbol, data_layer, context, notify_fn=sync_notify)
        return pipeline.run()

    await update.message.reply_text(f"Analyzing <b>{symbol}</b>...", parse_mode="HTML")

    result = await loop.run_in_executor(None, run_pipeline)

    # Build response message
    score_str = f"{result.score.total:.0f}/100" if result.score else "N/A"
    rec_emoji_map = {
        "PRIORITY": "\U0001f7e2", "PROPOSE": "\U0001f535", "WATCHLIST": "\U0001f7e1",
        "REJECTED": "\U0001f534", "BUY": "\U0001f7e2", "SELL": "\U0001f7e0", "IGNORE": "⚪",
    }
    rec_emoji = rec_emoji_map.get(result.recommendation, "⚪")

    msg_parts = [
        f"{rec_emoji} <b>{symbol}</b> — Score: {score_str} [{result.recommendation}]",
        f"Confidence: {result.llm_confidence:.0%}",
        "",
    ]

    if result.llm_narrative:
        msg_parts.append(result.llm_narrative)
        msg_parts.append("")

    if result.hard_rules and result.hard_rules.warnings:
        msg_parts.append("⚠️ " + " | ".join(result.hard_rules.warnings[:2]))
        msg_parts.append("")

    if result.hard_rules and not result.hard_rules.passed:
        msg_parts.append("❌ Blocked: " + "; ".join(result.hard_rules.failures[:2]))

    if not result.in_universe and result.recommendation in ("PROPOSE", "PRIORITY"):
        msg_parts.append("")
        msg_parts.append("\U0001f4a1 Add to universe?")
        msg_parts.append(f"<code>/proponer {symbol} score_{score_str}_favorable</code>")
    elif result.in_universe and result.recommendation in ("BUY", "PRIORITY"):
        msg_parts.append("")
        msg_parts.append("\U0001f4c8 Execute? Use:")
        msg_parts.append("<code>/si</code> to place order")

    msg = "\n".join(msg_parts)
    await update.message.reply_text(msg, parse_mode="HTML")

@_only_owner
async def cmd_proponer(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if len(ctx.args) < 2:
        await update.message.reply_text("Uso: /proponer SYMBOL razon")
        return
    symbol = ctx.args[0].upper()
    reason = " ".join(ctx.args[1:])
    data = _api("post", "/symbols/propose", json={"symbol": symbol, "reason": reason})
    await update.message.reply_text(data.get("message", f"{symbol} propuesto."))


@_only_owner
async def handle_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Maneja mensajes de texto libre -- pasa al LLM con contexto."""
    text = update.message.text
    await update.message.reply_text("Consultando al LLM...")
    prompt = (
        f"Eres el asistente del sistema IBKR AI Trader. El usuario dice: '{text}'\n\n"
        f"Tienes acceso a herramientas para ver precios, portafolio, cuenta, senales, "
        f"patrones aprendidos, simular y ejecutar ordenes. "
        f"Usa las que necesites segun la solicitud. "
        f"Responde en espanol de forma clara y concisa. "
        f"Si el usuario pide ejecutar una operacion, primero muestra preview_order y confirma."
    )
    loop = asyncio.get_event_loop()
    response = await loop.run_in_executor(None, _call_opencode, prompt)
    await update.message.reply_text(response[:4000])



@_only_owner
async def cmd_backtest(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await update.message.reply_text(
            "Uso: /backtest SYMBOL [DIAS]\n"
            "Ejemplo: /backtest AAPL 180\n"
            "Dias por defecto: 180"
        )
        return
    symbol = ctx.args[0].upper()
    days = int(ctx.args[1]) if len(ctx.args) > 1 else 180
    await update.message.reply_text(
        f"Corriendo backtest de {symbol} ({days} dias)...\n"
        "Esto puede tardar 30-60 segundos."
    )
    try:
        import httpx as _httpx
        r = _httpx.get(f"{API_BASE}/backtest/{symbol}?days={days}", timeout=120)
        if r.status_code == 200:
            data = r.json()
            from app.backtest.engine import BacktestResult
            from app.backtest.reporter import format_telegram
            result = BacktestResult(
                symbol=data["symbol"], period_days=data["period_days"],
                total_trades=data["total_trades"], wins=data["wins"],
                losses=data["losses"], win_rate=data["win_rate_pct"],
                total_pnl_usd=data["total_pnl_usd"], total_pnl_pct=data["total_pnl_pct"],
                profit_factor=data["profit_factor"], max_drawdown_pct=data["max_drawdown_pct"],
                avg_win_pct=data["avg_win_pct"], avg_loss_pct=data["avg_loss_pct"],
            )
            await update.message.reply_text(format_telegram(result))
        else:
            detail = r.json().get("detail", "Error desconocido")
            await update.message.reply_text(f"Error: {detail}")
    except Exception as e:
        await update.message.reply_text(f"Error al correr backtest: {e}")


@_only_owner
async def cmd_mercados(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    force = bool(ctx.args and ctx.args[0].lower() in ("refresh", "actualizar"))
    await update.message.reply_text("Consultando IB Gateway..." if force else "Cargando permisos de mercado...")
    loop = asyncio.get_event_loop()

    def run():
        from app.ibkr.market_permissions import get_permissions_report
        return get_permissions_report(force_refresh=force)

    report = await loop.run_in_executor(None, run)
    available = report["available"]
    unavailable = report["unavailable"]
    age = report["cache_age_hours"]
    age_str = f"{age:.1f}h" if age is not None else "nueva consulta"
    lines = ["Mercados y productos operables (cache: " + age_str + ")", ""]
    lines.append("Disponibles:")
    for p in available:
        exc = p["valid_exchanges"][:60] if p["valid_exchanges"] else "-"
        lines.append("  " + p["label"] + " (" + p["sec_type"] + "): " + exc)
    if unavailable:
        lines.append("")
        lines.append("No disponibles:")
        for p in unavailable:
            lines.append("  " + p["label"] + " (" + p["sec_type"] + "): no autorizado")
    lines.append("")
    lines.append("Usa /mercados refresh para forzar actualizacion.")
    await update.message.reply_text("\n".join(lines))

def start_bot(scheduler):
    """Arranca el bot en un nuevo event loop en thread separado."""
    if not TELEGRAM_BOT_TOKEN:
        logger.warning("TELEGRAM_BOT_TOKEN not set - bot not started")
        return

    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("estado", cmd_estado))
    app.add_handler(CommandHandler("posiciones", cmd_posiciones))
    app.add_handler(CommandHandler("historial", cmd_historial))
    app.add_handler(CommandHandler("senales", cmd_senales))
    app.add_handler(CommandHandler("simbolos", cmd_simbolos))
    app.add_handler(CommandHandler("pausar", cmd_pausar))
    app.add_handler(CommandHandler("reanudar", cmd_reanudar))
    app.add_handler(CommandHandler("stop", cmd_stop))
    app.add_handler(CommandHandler("cerrar", cmd_cerrar))
    app.add_handler(CommandHandler("modo", cmd_modo))
    app.add_handler(CommandHandler("aprobar", cmd_aprobar))
    app.add_handler(CommandHandler("ayuda", cmd_ayuda))
    app.add_handler(CommandHandler("diagnostico", cmd_diagnostico))
    app.add_handler(CommandHandler("analizar", cmd_analizar))
    app.add_handler(CommandHandler("proponer", cmd_proponer))
    app.add_handler(CommandHandler("mercados", cmd_mercados))
    app.add_handler(CommandHandler("backtest", cmd_backtest))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    logger.info("Telegram bot started with %d handlers", 18)
    try:
        import asyncio; loop = asyncio.new_event_loop(); asyncio.set_event_loop(loop); app.run_polling(drop_pending_updates=True, stop_signals=None, close_loop=True)
    except Exception as e:
        logger.error(f"Telegram bot error: {e}")
