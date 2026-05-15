# app/config/settings.py
import os
from dotenv import load_dotenv
load_dotenv()
from zoneinfo import ZoneInfo

# --- IB Gateway ---
IB_HOST = os.getenv("IB_HOST", "127.0.0.1")
IB_PORT = int(os.getenv("IB_PORT", "4002"))
IB_CLIENT_ID = 10
IB_CLIENT_ID_DATA = int(os.getenv("IB_CLIENT_ID_DATA", "12"))
MARKET_DATA_TYPE = 3  # 3=delayed, 1=live
IB_MOCK = os.getenv("IB_MOCK", "false").lower() == "true"

# --- Trading rules ---
READ_ONLY = True
PAPER_TRADING_ONLY = os.getenv("PAPER_TRADING_ONLY", "true").lower() == "true"
REQUIRE_HUMAN_APPROVAL = not PAPER_TRADING_ONLY
MAX_POSITIONS = 3
MAX_RISK_PCT = 0.02
MIN_RISK_USD = 1.0
MAX_POSITION_USD = 500.0
CAPITAL_CAP = float(os.getenv("CAPITAL_CAP", "500.0"))

# DEPRECATED — kept for backward-compat with any external script.
# The risk validator now reads approved symbols from the DB.
ALLOWED_SYMBOLS = [
    "AAPL", "MSFT", "SPY", "QQQ",
    "TSLA", "NVDA", "AMZN", "GOOGL",
    "META", "JPM",
]

# --- LLM ---
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.moonshot.cn/v1")
LLM_MODEL = os.getenv("LLM_MODEL", "moonshot-v1-8k")
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
OPENCODE_BIN = os.getenv("OPENCODE_BIN", "/home/frankpach/.opencode/bin/opencode")
OPENCODE_MODEL = os.getenv("OPENCODE_MODEL", "opencode-go/qwen3.5-plus")
OPENCODE_CWD = os.getenv("OPENCODE_CWD", "/home/frankpach/ibkr-bot")

# --- Internal API ---
API_BASE = os.getenv("API_BASE", "http://127.0.0.1:8088")
API_CONTROL_KEY = os.getenv("API_CONTROL_KEY", "")
API_ADMIN_KEY = os.getenv("API_ADMIN_KEY", "")

# --- Scheduler ---
SCAN_INTERVAL_MINUTES = 15
MARKET_TZ = ZoneInfo("America/New_York")
MARKET_OPEN_HOUR = 9
MARKET_OPEN_MINUTE = 15
MARKET_CLOSE_HOUR = 16
MARKET_CLOSE_MINUTE = 15

POSITION_CHECK_MINUTES = 2
MIN_PROFIT_PCT_MEDIUM = 0.01
ENTRY_SLIPPAGE_BUFFER: float = float(os.getenv("ENTRY_SLIPPAGE_BUFFER", "0.005"))

# --- Telegram ---
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
TELEGRAM_APPROVAL_TIMEOUT_SECONDS = 300

# --- DB ---
DB_PATH = os.getenv("DB_PATH", "ibkr_trader.db")
