# app/scanner/news.py
"""
Obtiene noticias recientes de Yahoo Finance RSS para un simbolo.
Proporciona contexto de sentiment al LLM antes de decidir.
"""
import logging
import feedparser

logger = logging.getLogger(__name__)

POSITIVE_WORDS = {
    "surge", "rally", "beat", "record", "high", "gain", "rise", "up",
    "strong", "growth", "profit", "bullish", "upgrade", "buy", "positive",
    "exceeds", "outperform", "boost", "jump", "soar", "breakout",
}
NEGATIVE_WORDS = {
    "crash", "fall", "drop", "loss", "miss", "low", "down", "weak",
    "decline", "recession", "fear", "risk", "cut", "downgrade", "sell",
    "bearish", "warning", "disappoint", "plunge", "slump", "layoff",
}


def _extract_sentiment(text: str) -> str:
    """Clasifica el sentimiento de un texto como positive/negative/neutral."""
    words = text.lower().split()
    pos = sum(1 for w in words if w.strip(".,!?") in POSITIVE_WORDS)
    neg = sum(1 for w in words if w.strip(".,!?") in NEGATIVE_WORDS)
    if pos > neg:
        return "positive"
    if neg > pos:
        return "negative"
    return "neutral"


def get_news_summary(symbol: str, max_items: int = 3) -> str:
    """
    Descarga las ultimas noticias de Yahoo Finance RSS para un simbolo.
    Retorna un resumen en texto para incluir en el prompt del LLM.
    """
    url = f"https://feeds.finance.yahoo.com/rss/2.0/headline?s={symbol}&region=US&lang=en-US"
    try:
        feed = feedparser.parse(url)
        entries = feed.entries[:max_items]

        if not entries:
            return f"No recent news found for {symbol}."

        lines = []
        for entry in entries:
            title = getattr(entry, "title", "")
            summary = getattr(entry, "summary", "")
            text = f"{title} {summary}"
            sentiment = _extract_sentiment(text)
            lines.append(f"[{sentiment.upper()}] {title}")

        return "\n".join(lines)

    except Exception as e:
        logger.error(f"Could not fetch news for {symbol}: {e}")
        return f"News unavailable for {symbol}."
