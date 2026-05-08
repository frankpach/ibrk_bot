# app/llm/agent.py
import json
import logging
from dataclasses import dataclass
from datetime import datetime
import httpx
from openai import OpenAI
from app.config.settings import LLM_BASE_URL, LLM_MODEL, LLM_API_KEY, MARKET_TZ
from app.db.database import get_patterns_for_symbol, insert_decision
from app.db.models import Decision

logger = logging.getLogger(__name__)
API_BASE = "http://127.0.0.1:8088"

TOOLS = [
    {"type": "function", "function": {
        "name": "get_price", "description": "Precio actual de un simbolo",
        "parameters": {"type": "object", "properties": {"symbol": {"type": "string"}}, "required": ["symbol"]},
    }},
    {"type": "function", "function": {
        "name": "get_portfolio", "description": "Posiciones abiertas",
        "parameters": {"type": "object", "properties": {}},
    }},
    {"type": "function", "function": {
        "name": "get_account", "description": "Balance y capital disponible",
        "parameters": {"type": "object", "properties": {}},
    }},
    {"type": "function", "function": {
        "name": "get_patterns", "description": "Patrones aprendidos para un simbolo",
        "parameters": {"type": "object", "properties": {"symbol": {"type": "string"}}, "required": ["symbol"]},
    }},
]


@dataclass
class LLMDecision:
    action: str
    stop_loss_pct: float
    take_profit_pct: float
    justification: str
    confidence: str


def _call_tool(name: str, args: dict) -> str:
    try:
        if name == "get_price":
            return httpx.get(f"{API_BASE}/price/{args['symbol']}", timeout=15).text
        elif name == "get_portfolio":
            return httpx.get(f"{API_BASE}/portfolio", timeout=15).text
        elif name == "get_account":
            return httpx.get(f"{API_BASE}/account", timeout=15).text
        elif name == "get_patterns":
            patterns = get_patterns_for_symbol(args["symbol"])
            return json.dumps([{"pattern": p.pattern_text, "wins": p.win_count, "losses": p.loss_count} for p in patterns])
    except Exception as e:
        return json.dumps({"error": str(e)})
    return json.dumps({"error": "unknown tool"})


def analyze_signal(symbol: str, strength: str, rsi: float, macd: float, volume_ratio: float, signal_id: int) -> LLMDecision:
    if not LLM_API_KEY:
        logger.warning("LLM_API_KEY not set - returning IGNORE")
        return LLMDecision("IGNORE", 0, 0, "LLM not configured", "LOW")

    llm = OpenAI(api_key=LLM_API_KEY, base_url=LLM_BASE_URL)
    system = """Eres un agente de swing trading. Analiza senales tecnicas y decide si entrar en una posicion.
REGLAS: take_profit debe ser al menos 2x el stop_loss. Si no hay evidencia suficiente, responde IGNORE.
FORMATO JSON estricto: {"action":"BUY"|"SELL"|"IGNORE","stop_loss_pct":0.025,"take_profit_pct":0.06,"justification":"...","confidence":"HIGH"|"MEDIUM"|"LOW"}"""

    user = f"Senal: {symbol} | Fuerza: {strength} | RSI: {rsi} | MACD: {macd} | Vol ratio: {volume_ratio}x\nUsa las herramientas para obtener precio, portafolio, capital y patrones aprendidos. Luego decide."

    messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]

    for _ in range(6):
        response = llm.chat.completions.create(
            model=LLM_MODEL, messages=messages, tools=TOOLS,
            tool_choice="auto", temperature=0.2,
        )
        msg = response.choices[0].message

        if msg.tool_calls:
            messages.append({"role": "assistant", "content": msg.content, "tool_calls": [
                {"id": tc.id, "type": "function", "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                for tc in msg.tool_calls
            ]})
            for tc in msg.tool_calls:
                messages.append({"role": "tool", "tool_call_id": tc.id,
                                  "content": _call_tool(tc.function.name, json.loads(tc.function.arguments))})
            continue

        try:
            content = msg.content.strip()
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
            data = json.loads(content)
            decision = LLMDecision(
                action=data.get("action", "IGNORE"),
                stop_loss_pct=float(data.get("stop_loss_pct", 0.02)),
                take_profit_pct=float(data.get("take_profit_pct", 0.04)),
                justification=data.get("justification", ""),
                confidence=data.get("confidence", "LOW"),
            )
            insert_decision(Decision(
                id=None, signal_id=signal_id, symbol=symbol, llm_model=LLM_MODEL,
                prompt_summary=user[:500], response=content, action=decision.action,
                stop_loss_pct=decision.stop_loss_pct, take_profit_pct=decision.take_profit_pct,
                created_at=datetime.now(tz=MARKET_TZ),
            ))
            logger.info(f"LLM: {symbol} -> {decision.action} SL:{decision.stop_loss_pct} TP:{decision.take_profit_pct}")
            return decision
        except (json.JSONDecodeError, KeyError) as e:
            logger.error(f"Failed to parse LLM response: {e}")
            break

    return LLMDecision("IGNORE", 0, 0, "Failed to parse LLM response", "LOW")
