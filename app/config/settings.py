# app/config/settings.py
"""Configuración centralizada del bot de trading."""
import os
from zoneinfo import ZoneInfo

# ── Trading ──
ALLOWED_SYMBOLS: list[str] = ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA", "NVDA", "META", "AMD"]
MAX_POSITIONS: int = int(os.getenv("MAX_POSITIONS", "5"))
MAX_RISK_PCT: float = float(os.getenv("MAX_RISK_PCT", "0.01"))      # 1% del capital por trade
MIN_RISK_USD: float = float(os.getenv("MIN_RISK_USD", "50"))          # Riesgo mínimo en USD
MAX_POSITION_USD: float = float(os.getenv("MAX_POSITION_USD", "5000")) # Máximo por posición
MIN_PROFIT_PCT_MEDIUM: float = float(os.getenv("MIN_PROFIT_PCT_MEDIUM", "0.015"))  # 1.5%
MAX_DAILY_LOSS_PCT: float = float(os.getenv("MAX_DAILY_LOSS_PCT", "0.03"))         # 3% diario

# ── Mercado ──
MARKET_TZ = ZoneInfo("America/New_York")
MARKET_OPEN_HOUR: int = 9
MARKET_OPEN_MINUTE: int = 30
MARKET_CLOSE_HOUR: int = 16
MARKET_CLOSE_MINUTE: int = 0

# ── IBKR ──
IB_GATEWAY_HOST: str = os.getenv("IB_GATEWAY_HOST", "127.0.0.1")
IB_GATEWAY_PORT: int = int(os.getenv("IB_GATEWAY_PORT", "7497"))
IB_CLIENT_ID: int = int(os.getenv("IB_CLIENT_ID", "11"))

# ── LLM ──
LLM_API_KEY: str | None = os.getenv("LLM_API_KEY")
LLM_BASE_URL: str = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
LLM_MODEL: str = os.getenv("LLM_MODEL", "gpt-4o-mini")

# ── Base de datos ──
DB_PATH: str = os.getenv("DB_PATH", "data/trades.db")

# ── Seguridad / Modo ──
PAPER_TRADING_ONLY: bool = os.getenv("PAPER_TRADING_ONLY", "true").lower() in ("1", "true", "yes")
REQUIRE_HUMAN_APPROVAL: bool = os.getenv("REQUIRE_HUMAN_APPROVAL", "false").lower() in ("1", "true", "yes")

# ── Scheduler ──
SCAN_INTERVAL_MINUTES: int = int(os.getenv("SCAN_INTERVAL_MINUTES", "15"))
POSITION_CHECK_MINUTES: int = int(os.getenv("POSITION_CHECK_MINUTES", "5"))
SYNC_INTERVAL_MINUTES: int = int(os.getenv("SYNC_INTERVAL_MINUTES", "10"))

# ── Notificaciones ──
TELEGRAM_BOT_TOKEN: str | None = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID: str | None = os.getenv("TELEGRAM_CHAT_ID")

# ── Misc ──
MIN_RR_RATIO: float = float(os.getenv("MIN_RR_RATIO", "2.0"))  # Mínimo reward/risk
