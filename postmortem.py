# app/llm/postmortem.py
"""
Análisis post-mortem de trades cerrados.
Llama al LLM para extraer un patrón aprendido y lo guarda en DB.
"""
import logging
from datetime import datetime

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

    outcome = "GANANCIA" if (trade.pnl_pct or 0) >= 0 else "PERDIDA"
    prompt = (
        f"Analiza esta operacion de trading cerrada y extrae UN patron aprendido conciso.\n\n"
        f"Simbolo: {trade.symbol}\n"
        f"Accion: {trade.action}\n"
        f"Senal: {trade.signal_strength}\n"
        f"Justificacion original: {trade.llm_justification}\n"
        f"Entrada: ${trade.entry_price:.2f}\n"
        f"Stop-loss: ${trade.stop_loss_price:.2f} ({trade.stop_loss_pct:.1%})\n"
        f"Take-profit: ${trade.take_profit_price:.2f} ({trade.take_profit_pct:.1%})\n"
        f"Resultado: {outcome}\n"
        f"PnL: {trade.pnl_pct:.2%} (${trade.pnl_usd:.2f})\n"
        f"Razon de cierre: {trade.exit_reason}\n\n"
        f"Responde SOLO con una frase corta que describa el patron aprendido.\n"
        f'Ejemplo: "AAPL + RSI<30 + MACD alcista -> BUY confiable en apertura"'
    )

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
