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
    acc = _api("get", "/account") or {}

    if isinstance(portfolio, list) and portfolio:
        pos_text = "\n".join(
            f"  {p['symbol']}: {p['quantity']} acc @ ${p['avg_cost']:.2f} | P&L: ${p['unrealized_pnl']:.2f}"
            for p in portfolio
        )
    else:
        pos_text = "  Sin posiciones abiertas"

    ib_status = "✅ Conectado" if data.get('ib_connected') else "❌ Desconectado"
    real_cap = acc.get("net_liquidation", 0)
    op_cap = data.get("operating_capital", real_cap)

    msg = (
        f"Estado del sistema\n\n"
        f"IB Gateway: {ib_status}\n"
        f"Modo: {data.get('mode', '?').upper()}\n"
        f"Pausado: {'Si' if data.get('paused') else 'No'}\n"
        f"Capital real IB: ${real_cap:,.2f}\n"
        f"Capital operativo: ${op_cap:,.2f}\n"
        f"P&L hoy (DB local): ${data.get('daily_pnl_usd', 0):.2f} ({data.get('daily_pnl_pct', 0):.2f}%)\n"
        f"Posiciones abiertas (IBKR): {len(portfolio) if isinstance(portfolio, list) else '?'}/3\n\n"
        f"Posiciones abiertas:\n{pos_text}"
    )
    await update.message.reply_text(msg)


@_only_owner
async def cmd_posiciones(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    # Fuente de verdad: IBKR real
    portfolio = _api("get", "/portfolio")
    if portfolio is None:
        portfolio = []
    if not isinstance(portfolio, list):
        portfolio = []

    # Cruzar con DB local para SL/TP si existen
    local_trades = _api("get", "/trades") or []
    local_map = {t["symbol"]: t for t in local_trades if isinstance(t, dict)}

    if not portfolio:
        # Si IBKR no tiene pero la DB local sí, alertar
        if local_trades:
            await update.message.reply_text(
                "IBKR: Sin posiciones abiertas.\n"
                f"⚠️ Pero hay {len(local_trades)} trade(s) en DB local que parecen huérfanos.\n"
                "Usa /diagnostico para revisar."
            )
        else:
            await update.message.reply_text("Sin posiciones abiertas en IBKR.")
        return

    lines = ["Posiciones abiertas (IBKR):"]
    for p in portfolio:
        sym = p.get("symbol", "?")
        qty = p.get("quantity", 0)
        avg = p.get("avg_cost", 0)
        mkt = p.get("market_value", 0)
        pnl = p.get("unrealized_pnl", 0)
        emoji = "🟢" if pnl >= 0 else "🔴"
        t = local_map.get(sym)
        if t:
            sl = t.get("stop_loss_price")
            tp = t.get("take_profit_price")
            extra = f"  SL: ${sl:.2f} | TP: ${tp:.2f} | DB local"
        else:
            extra = "  ⚠️ No hay registro local (SL/TP desconocidos)"
        lines.append(
            f"{emoji} {sym}: {qty} acc @ ${avg:.2f} | Mkt: ${mkt:.2f} | P&L: ${pnl:.2f}\n{extra}"
        )

    # Alertar si hay trades locales sin posición en IBKR
    orphaned = [s for s in local_map if s not in {x.get("symbol") for x in portfolio}]
    if orphaned:
        lines.append("")
        lines.append(f"⚠️ DB local tiene trades sin posición IBKR: {', '.join(orphaned)}")

    await update.message.reply_text("\n".join(lines))


@_only_owner
async def cmd_historial(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    # Intentar IBKR real primero
    ibkr = _api("get", "/executions?limit=5")
    lines = []
    source = None

    if ibkr and isinstance(ibkr, dict) and ibkr.get("count", 0) > 0 and not ibkr.get("error"):
        source = "IBKR"
        lines.append("Ultimas operaciones (IBKR real):")
        for e in ibkr["executions"]:
            pnl = e.get("realized_pnl")
            pnl_str = f" | P&L: ${pnl:.2f}" if pnl is not None else ""
            lines.append(
                f"{e['action']} {e['symbol']} x{e['quantity']} @ ${e['price']:.2f}{pnl_str}\n"
                f"  {e.get('time','')}"
            )
    else:
        # Fallback a DB local
        trades = _api("get", "/trades/closed?limit=5")
        if trades and isinstance(trades, list) and len(trades) > 0:
            source = "local"
            lines.append("Ultimas operaciones (historial LOCAL — IBKR no disponible):")
            for t in trades:
                pnl = t.get("pnl_usd") or 0
                emoji = "+" if pnl >= 0 else "-"
                lines.append(f"{emoji} {t['symbol']} {t['action']} | ${pnl:.2f} ({t.get('exit_reason','?')})")
        else:
            await update.message.reply_text("Sin historial de operaciones (ni en IBKR ni en DB local).")
            return

    await update.message.reply_text("\n".join(lines))


@_only_owner
async def cmd_senales(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    signals = _api("get", "/signals?since_hours=24")
    if not signals or not isinstance(signals, list):
        await update.message.reply_text("Sin senales pendientes en las ultimas 24h.")
        return
    lines = [f"Senales pendientes (ultimas 24h): {len(signals)}", ""]
    for s in signals:
        age = s.get("created_at", "?")
        lines.append(
            f"{s['symbol']} [{s['strength']}] RSI:{s.get('rsi','?')} Vol:{s.get('volume_ratio','?')}x\n"
            f"  Creada: {age}"
        )
    await update.message.reply_text("\n".join(lines))


@_only_owner
async def cmd_simbolos(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    data = _api("get", "/allowed-symbols")
    symbols = data.get("symbols", [])
    meta = data.get("meta", [])
    if not symbols:
        await update.message.reply_text("Universo activo vacio. Ningun simbolo aprobado en la DB.")
        return
    lines = [f"Universo activo: {len(symbols)} simbolos", ""]
    for m in meta:
        lines.append(
            f"{m['symbol']} ({m.get('market_key','?')}) — {m.get('sec_type','?')}/{m.get('exchange','?')}"
        )
    await update.message.reply_text("\n".join(lines))


@_only_owner
async def cmd_costos(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Muestra comisiones reales y P&L del historial de IBKR."""
    data = _api("get", "/account/commission-report") or {}
    fills = data.get("fills", [])
    total_comm = data.get("total_commission", 0)
    total_pnl = data.get("total_realized_pnl", 0)
    fill_count = data.get("fill_count", 0)

    if fill_count == 0:
        await update.message.reply_text(
            "Sin historial de ejecuciones en IBKR (ultimos 30 dias).\n"
            "Esto puede significar que no hay operaciones, o que IB Gateway "
            "no tiene permisos para leer el historial."
        )
        return

    lines = [
        "REPORTE DE COSTOS REALES (IBKR)",
        "",
        f"Total ejecuciones: {fill_count}",
        f"Total comisiones:  ${total_comm:,.2f}",
        f"Total P&L realizado: ${total_pnl:,.2f}",
        f"Neto despues de fees: ${total_pnl - total_comm:,.2f}",
        "",
        "Ultimas 5 operaciones:",
    ]
    for f in fills[:5]:
        pnl_str = f" | P&L: ${f['realized_pnl']:.2f}" if f.get('realized_pnl') is not None else ""
        lines.append(
            f"{f['action']} {f['symbol']} x{f['quantity']} @ ${f['price']:.2f}\n"
            f"  Comision: ${f['commission']:.2f}{pnl_str}\n"
            f"  {f.get('time','')}"
        )

    # Proyeccion para $39
    if total_comm > 0 and fill_count > 0:
        avg_comm_per_trade = total_comm / fill_count
        lines.append("")
        lines.append("--- Proyeccion con tu capital ($39) ---")
        lines.append(f"Comision promedio por operacion: ${avg_comm_per_trade:.2f}")
        lines.append(f"Costo round-trip (buy+sell): ${avg_comm_per_trade * 2:.2f}")
        lines.append(f"Capital necesario para cubrir 1 round-trip: ${avg_comm_per_trade * 2 + 1:.2f}")
        if avg_comm_per_trade * 2 > 39 * 0.05:
            lines.append("⚠️ Las comisiones superan tu riesgo maximo por trade (5% = $1.95)")

    await update.message.reply_text("\n".join(lines))


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
    from datetime import datetime, timezone

    lines = ["DIAGNOSTICO DEL SISTEMA", ""]

    # Capital operativo (IBKR real)
    acc = _api("get", "/account") or {}
    real_cap = acc.get("net_liquidation", 0)
    op_cap = min(real_cap, CAPITAL_CAP)
    lines.append(f"Capital real IB:    ${real_cap:,.2f}")
    lines.append(f"Capital operativo:  ${op_cap:,.2f} (cap=${CAPITAL_CAP:.0f})")
    lines.append("")

    # Posiciones reales IBKR
    portfolio = _api("get", "/portfolio") or []
    if isinstance(portfolio, list):
        lines.append(f"Posiciones abiertas (IBKR): {len(portfolio)}")
        for p in portfolio:
            pnl = p.get("unrealized_pnl", 0)
            emoji = "🟢" if pnl >= 0 else "🔴"
            lines.append(
                f"  {emoji} {p['symbol']}: {p['quantity']} @ ${p['avg_cost']:.2f} | P&L: ${pnl:.2f}"
            )
    else:
        lines.append("Posiciones abiertas (IBKR): error al consultar")
    lines.append("")

    conn = get_connection()
    try:
        signals_total = conn.execute("SELECT COUNT(*) FROM signals").fetchone()[0]
        signals_pending = conn.execute("SELECT COUNT(*) FROM signals WHERE processed=0").fetchone()[0]
        trades_closed = conn.execute("SELECT COUNT(*) FROM trades WHERE status='CLOSED'").fetchone()[0]
        trades_open_local = conn.execute("SELECT COUNT(*) FROM trades WHERE status='OPEN'").fetchone()[0]
        patterns_count = conn.execute("SELECT COUNT(*) FROM patterns").fetchone()[0]

        last_signal = conn.execute(
            "SELECT symbol, strength, created_at FROM signals ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
        last_decision = conn.execute(
            "SELECT symbol, action, created_at FROM decisions ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
        last_trade = conn.execute(
            "SELECT symbol, status, closed_at, opened_at FROM trades ORDER BY closed_at DESC, opened_at DESC LIMIT 1"
        ).fetchone()
    finally:
        conn.close()

    lines.append("--- Datos locales (DB) ---")
    lines.append(f"Senales totales:     {signals_total} ({signals_pending} pendientes)")
    lines.append(f"Trades cerrados:     {trades_closed}")
    lines.append(f"Trades abiertos DB:  {trades_open_local}")
    lines.append(f"Patrones:            {patterns_count}")
    lines.append("")

    if last_signal:
        age = "?"
        try:
            dt = datetime.fromisoformat(last_signal["created_at"])
            age = str(datetime.now(timezone.utc) - dt).split(".")[0]
        except Exception:
            pass
        lines.append(f"Ultima senal: {last_signal['symbol']} [{last_signal['strength']}] (hace {age})")
    else:
        lines.append("Ultima senal: ninguna")

    if last_decision:
        age = "?"
        try:
            dt = datetime.fromisoformat(last_decision["created_at"])
            age = str(datetime.now(timezone.utc) - dt).split(".")[0]
        except Exception:
            pass
        lines.append(f"Ultima decision: {last_decision['symbol']} -> {last_decision['action']} (hace {age})")
    else:
        lines.append("Ultima decision: ninguna")

    if last_trade:
        ts = last_trade.get("closed_at") or last_trade.get("opened_at")
        age = "?"
        try:
            dt = datetime.fromisoformat(ts)
            age = str(datetime.now(timezone.utc) - dt).split(".")[0]
        except Exception:
            pass
        lines.append(f"Ultimo trade: {last_trade['symbol']} ({last_trade['status']}) (hace {age})")
    else:
        lines.append("Ultimo trade: ninguno")

    lines.append("")
    connected = (_api("get", "/health") or {}).get("connected", False)
    lines.append("IB Gateway: " + ("✅ conectado" if connected else "❌ DESCONECTADO"))

    await update.message.reply_text("\n".join(lines))

@_only_owner
async def cmd_ayuda(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Comandos disponibles:\n\n"
        "📊 Informacion:\n"
        "  /estado — resumen del sistema\n"
        "  /diagnostico — estado completo: capital, senales, patrones\n"
        "  /posiciones — posiciones abiertas\n"
        "  /historial — ultimas 5 operaciones\n"
        "  /senales — senales pendientes\n"
        "  /simbolos — universo de trading aprobado\n"
        "  /mercados — estado de mercados por asset class\n\n"
        "⚙️ Control:\n"
        "  /pausar — detener el scanner\n"
        "  /reanudar — reactivar el scanner\n"
        "  /cerrar SYMBOL — cerrar posicion\n"
        "  /cerrar todo — cerrar todas las posiciones\n"
        "  /modo paper|live — cambiar modo de trading\n"
        "  /aprobar SYMBOL — aprobar simbolo para trading\n"
        "  /stop — detener el sistema\n\n"
        "🤖 Analisis con IA:\n"
        "  /analizar SYMBOL — analisis completo con LLM\n"
        "  /proponer SYMBOL razon — proponer simbolo nuevo\n"
        "  /backtest SYMBOL — backtest historico del simbolo\n"
        "  Cualquier mensaje de texto — consulta libre al LLM\n\n"
        "🔔 Notificaciones:\n"
        "  /notificaciones critico|normal|verbose — nivel de ruido\n"
        "  /silencio N — silenciar N horas (solo criticos pasan)\n\n"
        "⚡ Alertas de precio:\n"
        "  /alerta SYMBOL UMBRAL — crear alerta (ej: /alerta TSLA 5%)\n"
        "  /alertas — ver alertas activas\n"
        "  /eliminar_alerta ID — eliminar alerta"
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

    # Dimension breakdown for transparency
    dim_lines = []
    if result.score:
        dim_map = {
            "momentum": "Momentum", "trend": "Trend", "volume": "Volume",
            "volatility": "Volatility", "portfolio_fit": "Portfolio",
            "sentiment": "Sentiment", "price_change": "Price Δ",
        }
        for key, label in dim_map.items():
            val = getattr(result.score, key, None)
            if val is not None:
                bar = "█" * int(val * 10) + "░" * (10 - int(val * 10))
                dim_lines.append(f"  {label:12s} {bar} {val:.2f}")

    msg_parts = [
        f"{rec_emoji} <b>{symbol}</b> — Score: {score_str} [{result.recommendation}]",
        f"Confidence: {result.llm_confidence:.0%}",
        "",
    ]

    if dim_lines:
        msg_parts.append("Dimensiones:")
        msg_parts.extend(dim_lines)
        msg_parts.append("")

    if result.llm_narrative:
        msg_parts.append(result.llm_narrative)
        msg_parts.append("")

    if result.hard_rules and result.hard_rules.warnings:
        msg_parts.append("⚠️ " + " | ".join(result.hard_rules.warnings[:2]))
        msg_parts.append("")

    if result.hard_rules and not result.hard_rules.passed:
        msg_parts.append("❌ Blocked: " + "; ".join(result.hard_rules.failures[:2]))

    if result.recommendation == "ERROR":
        msg_parts.append("")
        msg_parts.append(f"❌ Error en análisis: {result.failed_at_step or 'unknown'}")
        msg_parts.append("Reintenta con /analizar o revisa /diagnostico")

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
async def cmd_notificaciones(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Change notification level: /notificaciones critico|normal|verbose"""
    from app.notifications.policy import get_policy
    args = ctx.args
    if not args:
        await update.message.reply_text("Uso: /notificaciones critico|normal|verbose")
        return
    nivel = args[0].lower()
    level_map = {"critico": "critical_only", "normal": "normal", "verbose": "verbose"}
    if nivel not in level_map:
        await update.message.reply_text(f"Nivel inválido: {nivel}. Usar: critico|normal|verbose")
        return
    get_policy().set_level(level_map[nivel])
    await update.message.reply_text(f"✅ Nivel de notificaciones: {level_map[nivel]}")


@_only_owner
async def cmd_silencio(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Suppress non-critical notifications for N hours: /silencio 2"""
    import threading
    from app.notifications.policy import get_digest_generator
    args = ctx.args
    try:
        horas = int(args[0]) if args else 1
    except (ValueError, IndexError):
        horas = 1
    gen = get_digest_generator()
    gen.start_suppression()
    def restore():
        gen.end_suppression()
    threading.Timer(horas * 3600, restore).start()
    await update.message.reply_text(f"🔕 Silencio activado por {horas}h (solo críticos)")


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
    app.add_handler(CommandHandler("notificaciones", cmd_notificaciones))
    app.add_handler(CommandHandler("silencio", cmd_silencio))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    logger.info("Telegram bot started with %d handlers", 20)
    try:
        import asyncio; loop = asyncio.new_event_loop(); asyncio.set_event_loop(loop); app.run_polling(drop_pending_updates=True, stop_signals=None, close_loop=True)
    except Exception as e:
        logger.error(f"Telegram bot error: {e}")
