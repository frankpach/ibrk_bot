# app/llm/agent.py
"""
Agente LLM usando OpenCode como backend (sin API key externa).
Llama a `opencode run` via subprocess con el modelo configurado.
"""
import json
import logging
import subprocess
from dataclasses import dataclass
from datetime import datetime

import httpx

from app.config.settings import MARKET_TZ
from app.infrastructure.db.compat import get_patterns_for_symbol, insert_decision
from app.db.models import Decision
from app.scanner.news import get_news_summary

logger = logging.getLogger(__name__)

from app.config.settings import API_BASE  # noqa: F401
from app.config.settings import OPENCODE_BIN  # noqa: F401
from app.config.settings import OPENCODE_MODEL as _DEFAULT_OPENCODE_MODEL


def get_llm_model_for_task(task: str = "analysis") -> str:
    """Read per-task LLM model from control_settings DB, fallback to env/config default."""
    key_map = {
        "analysis":   "llm_model_analysis",
        "signal":     "llm_model_signal",
        "postmortem": "llm_model_postmortem",
    }
    key = key_map.get(task, "opencode_model")
    try:
        from app.infrastructure.db.compat import get_control_setting_value
        val = get_control_setting_value(key, _DEFAULT_OPENCODE_MODEL)
        return val if val else _DEFAULT_OPENCODE_MODEL
    except Exception:
        return _DEFAULT_OPENCODE_MODEL

# Categorias de simbolos y sus estrategias
SYMBOL_CATEGORIES = {
    "etf": ["SPY", "QQQ"],
    "blue_chip": ["AAPL", "MSFT", "GOOGL", "AMZN", "META", "JPM"],
    "growth": ["TSLA", "NVDA"],
}

STRATEGY_CONTEXTS = {
    "etf": (
        "Este simbolo es un ETF. Estrategia conservadora: "
        "sigue la tendencia macro, evita entrar contra la tendencia del mercado. "
        "Stop-loss mas ajustado (1.5-2%). Solo entrar con senal STRONG en los 3 timeframes."
    ),
    "blue_chip": (
        "Este simbolo es una empresa blue chip solida. Estrategia moderada: "
        "los fundamentales son importantes, los swings pueden durar mas tiempo. "
        "Stop-loss moderado (2-3%). Puedes entrar con senal MEDIUM si los patrones son consistentes."
    ),
    "growth": (
        "Este simbolo es una accion de alto crecimiento y alta volatilidad. Estrategia mas agresiva: "
        "los movimientos son mas bruscos, la volatilidad es alta. "
        "Stop-loss mas amplio (2.5-4%) para evitar salidas prematuras. "
        "Solo entrar con senal STRONG y noticias neutrales o positivas."
    ),
}


def get_symbol_category(symbol: str) -> str:
    sym = symbol.upper()
    for category, symbols in SYMBOL_CATEGORIES.items():
        if sym in symbols:
            return category
    return "blue_chip"


def get_strategy_context(category: str) -> str:
    return STRATEGY_CONTEXTS.get(category, STRATEGY_CONTEXTS["blue_chip"])


@dataclass
class LLMDecision:
    action: str           # BUY | SELL | IGNORE
    stop_loss_pct: float
    take_profit_pct: float
    justification: str
    confidence: str       # HIGH | MEDIUM | LOW


# --- Data Layer singleton ---

_data_layer_instance = None


def get_data_layer():
    """Returns singleton IBDataLayer. Uses MockIBClient if IB_MOCK=true."""
    global _data_layer_instance
    if _data_layer_instance is None:
        from app.config.settings import IB_MOCK
        from app.analysis.data import IBDataLayer
        if IB_MOCK:
            from app.analysis.mock_client import MockIBClient
            _data_layer_instance = IBDataLayer(MockIBClient())
        else:
            try:
                from app.ibkr.client import get_client
                _data_layer_instance = IBDataLayer(get_client())
            except Exception as e:
                logger.warning(f"Could not create IBKRClient for data layer: {e}")
                from app.analysis.mock_client import MockIBClient
                _data_layer_instance = IBDataLayer(MockIBClient())
    return _data_layer_instance


def analyze_signal(
    symbol: str, strength: str, rsi: float, macd: float,
    volume_ratio: float, signal_id: int
) -> LLMDecision:
    """Analyze a signal using AnalysisPipeline. Returns LLMDecision for backwards compat."""
    try:
        from app.analysis.pipeline import AnalysisPipeline, AnalysisContext
        from app.notifications.telegram import notify
        from app.container import get_container

        data_layer = get_data_layer()
        context = AnalysisContext(mode="auto_signal")
        _c = get_container()
        pipeline = AnalysisPipeline(symbol, data_layer, context, notify_fn=notify,
                                    broker=_c.broker, event_bus=_c.event_bus)
        result = pipeline.run()

        # Map AnalysisResult recommendation to LLMDecision for backwards compat
        action_map = {"BUY": "BUY", "SELL": "SELL", "IGNORE": "IGNORE",
                      "WATCHLIST": "IGNORE", "PROPOSE": "IGNORE",
                      "REJECTED": "IGNORE", "PRIORITY": "BUY", "ERROR": "IGNORE"}
        action = action_map.get(result.recommendation, "IGNORE")

        # Get SL/TP from symbol parameters or defaults
        try:
            from app.infrastructure.db.compat import get_or_create_symbol_parameters
            params = get_or_create_symbol_parameters(symbol)
            sl = params.stop_loss_pct if params else 0.025
            tp = params.take_profit_pct if params else 0.06
        except Exception:
            sl, tp = 0.025, 0.06

        if result.llm_confidence >= 0.75:
            conf = "HIGH"
        elif result.llm_confidence >= 0.5:
            conf = "MEDIUM"
        else:
            conf = "LOW"

        justification = (
            result.llm_narrative
            or (f"Score: {result.score.total:.0f}/100" if result.score else "No analysis")
        )

        decision = LLMDecision(
            action=action,
            stop_loss_pct=sl,
            take_profit_pct=tp,
            justification=justification,
            confidence=conf,
        )

        # Log to decisions table for backwards compat
        insert_decision(Decision(
            id=None, signal_id=signal_id, symbol=symbol,
            llm_model=get_llm_model_for_task("analysis"),
            prompt_summary=f"Pipeline mode=auto_signal score={result.score.total if result.score else 0:.0f}",
            response=str(result.to_dict())[:500],
            action=decision.action,
            stop_loss_pct=decision.stop_loss_pct,
            take_profit_pct=decision.take_profit_pct,
            created_at=datetime.now(tz=MARKET_TZ),
        ))

        return decision

    except Exception as e:
        logger.error(f"analyze_signal failed for {symbol}: {e}")
        return LLMDecision("IGNORE", 0.025, 0.06, f"Pipeline error: {e}", "LOW")


def build_llm_prompt(
    features,
    score: float,
    capital: float,
    price: float,
    patterns: list,
) -> str:
    """Construye el prompt completo para el LLM con todos los indicadores."""
    pattern_block = ""
    if patterns:
        pattern_block = "\nPATRONES APRENDIDOS (historial de este simbolo):\n"
        for p in patterns[:5]:
            pattern_block += f"  - {p}\n"

    def _fmt(val, fmt=".4f"):
        return format(val, fmt) if val is not None else "N/A"

    sma_block = (
        f"  SMA20 / SMA50 / SMA200: {_fmt(features.sma20, '.2f')} / "
        f"{_fmt(features.sma50, '.2f')} / {_fmt(features.sma200, '.2f')}\n"
    )

    return (
        "Eres un trader algoritmico. Analiza la siguiente senal tecnica"
        " y decide si operar.\n\n"
        f"SIMBOLO: {features.symbol} | PRECIO ACTUAL: ${price:.2f}\n"
        f"CAPITAL DISPONIBLE: ${capital:.2f}\n"
        f"SCORE CUANTITATIVO: {score:.0f}/100\n\n"
        "INDICADORES TECNICOS:\n"
        f"  RSI(14):          {_fmt(features.rsi_14, '.2f')}\n"
        f"  MACD line:        {_fmt(features.macd_line)}\n"
        f"  MACD signal:      {_fmt(features.macd_signal)}\n"
        f"  MACD crossover:   {features.macd_crossover}\n"
        f"  ATR %:            {_fmt(features.atr_pct, '.2f')}\n"
        + sma_block
        + f"  Bollinger pos:    {_fmt(features.bollinger_position, '.4f')}"
          f" (0=lower band, 1=upper band)\n"
        f"  Volume ratio 20d: {_fmt(features.volume_ratio_20d, '.2f')}x\n"
        f"  Hist vol 30d:     {_fmt(features.hist_volatility_30d, '.4f')}\n"
        f"  Impl vol:         {_fmt(features.impl_volatility, '.4f')}\n"
        f"  RS vs SPY 30d:    {_fmt(features.rs_vs_spy_30d, '.4f')}\n"
        f"  RS vs QQQ 30d:    {_fmt(features.rs_vs_qqq_30d, '.4f')}\n"
        + pattern_block
        + "\nREGLAS OBLIGATORIAS:\n"
          "  - take_profit_pct debe ser >= 2x stop_loss_pct\n"
          "  - Si la senal no es clara, elige IGNORE\n"
          "  - Justifica en maximo 2 oraciones\n\n"
          "Responde UNICAMENTE con este JSON:\n"
          '{"action": "BUY|SELL|IGNORE", "stop_loss_pct": 0.025, '
          '"take_profit_pct": 0.05, "justification": "...", "confidence": "HIGH|MEDIUM|LOW"}'
    )
