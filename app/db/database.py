# app/db/database.py
import sqlite3
import json
from datetime import datetime
from app.config.settings import DB_PATH, ALLOWED_SYMBOLS
from app.db.models import Signal, Trade, Pattern, Decision


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


# ----- Multi-market symbol universe (Plan A seed) ----------------------------
_STK_US_SEED = [
    ("AAPL", "STK", "SMART", "USD", "STK_US"),
    ("MSFT", "STK", "SMART", "USD", "STK_US"),
    ("SPY",  "STK", "SMART", "USD", "STK_US"),
    ("QQQ",  "STK", "SMART", "USD", "STK_US"),
    ("NVDA", "STK", "SMART", "USD", "STK_US"),
    ("TSLA", "STK", "SMART", "USD", "STK_US"),
    ("AMZN", "STK", "SMART", "USD", "STK_US"),
    ("GOOGL","STK", "SMART", "USD", "STK_US"),
    ("META", "STK", "SMART", "USD", "STK_US"),
    ("JPM",  "STK", "SMART", "USD", "STK_US"),
]

_FUT_US_SEED = [
    ("ES",  "FUT", "CME",   "USD", "FUT_US"),
    ("NQ",  "FUT", "CME",   "USD", "FUT_US"),
    ("YM",  "FUT", "CBOT",  "USD", "FUT_US"),
    ("RTY", "FUT", "CME",   "USD", "FUT_US"),
    ("CL",  "FUT", "NYMEX", "USD", "FUT_US"),
    ("GC",  "FUT", "COMEX", "USD", "FUT_US"),
    ("SI",  "FUT", "COMEX", "USD", "FUT_US"),
    ("NG",  "FUT", "NYMEX", "USD", "FUT_US"),
    ("ZB",  "FUT", "CBOT",  "USD", "FUT_US"),
    ("ZN",  "FUT", "CBOT",  "USD", "FUT_US"),
]

_CASH_FX_SEED = [
    ("EURUSD", "CASH", "IDEALPRO", "USD", "CASH_FX"),
    ("GBPUSD", "CASH", "IDEALPRO", "USD", "CASH_FX"),
    ("USDJPY", "CASH", "IDEALPRO", "JPY", "CASH_FX"),
    ("AUDUSD", "CASH", "IDEALPRO", "USD", "CASH_FX"),
    ("USDCAD", "CASH", "IDEALPRO", "CAD", "CASH_FX"),
    ("USDCHF", "CASH", "IDEALPRO", "CHF", "CASH_FX"),
    ("NZDUSD", "CASH", "IDEALPRO", "USD", "CASH_FX"),
    ("EURJPY", "CASH", "IDEALPRO", "JPY", "CASH_FX"),
    ("GBPJPY", "CASH", "IDEALPRO", "JPY", "CASH_FX"),
    ("EURGBP", "CASH", "IDEALPRO", "GBP", "CASH_FX"),
]

_CRYPTO_SEED = [
    ("BTC",  "CRYPTO", "PAXOS", "USD", "CRYPTO"),
    ("ETH",  "CRYPTO", "PAXOS", "USD", "CRYPTO"),
    ("LTC",  "CRYPTO", "PAXOS", "USD", "CRYPTO"),
    ("SOL",  "CRYPTO", "PAXOS", "USD", "CRYPTO"),
    ("ADA",  "CRYPTO", "PAXOS", "USD", "CRYPTO"),
    ("AVAX", "CRYPTO", "PAXOS", "USD", "CRYPTO"),
    ("DOT",  "CRYPTO", "PAXOS", "USD", "CRYPTO"),
    ("LINK", "CRYPTO", "PAXOS", "USD", "CRYPTO"),
    ("XRP",  "CRYPTO", "PAXOS", "USD", "CRYPTO"),
    ("UNI",  "CRYPTO", "PAXOS", "USD", "CRYPTO"),
]

_FULL_SEED = _STK_US_SEED + _FUT_US_SEED + _CASH_FX_SEED + _CRYPTO_SEED


def _add_column_if_missing(conn, table: str, column: str, ddl: str) -> None:
    """SQLite has no IF NOT EXISTS for ADD COLUMN - try/except instead."""
    try:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")
    except Exception as exc:
        if "duplicate column name" not in str(exc).lower():
            raise


def _migrate_symbol_config(conn) -> None:
    _add_column_if_missing(conn, "symbol_config", "sec_type",     "TEXT DEFAULT 'STK'")
    _add_column_if_missing(conn, "symbol_config", "exchange",     "TEXT DEFAULT 'SMART'")
    _add_column_if_missing(conn, "symbol_config", "currency",     "TEXT DEFAULT 'USD'")
    _add_column_if_missing(conn, "symbol_config", "liquid_hours", "TEXT")
    _add_column_if_missing(conn, "symbol_config", "market_key",   "TEXT DEFAULT 'STK_US'")


def _seed_symbol_universe(conn) -> None:
    from datetime import timezone
    now = datetime.now(timezone.utc).isoformat()
    for sym, sec_type, exch, ccy, market_key in _FULL_SEED:
        conn.execute(
            """
            INSERT INTO symbol_config
                (symbol, extra_indicators, approved, proposed_by, created_at,
                 sec_type, exchange, currency, market_key)
            VALUES (?, '[]', 1, 'seed', ?, ?, ?, ?, ?)
            ON CONFLICT(symbol) DO UPDATE SET
                sec_type   = excluded.sec_type,
                exchange   = excluded.exchange,
                currency   = excluded.currency,
                market_key = excluded.market_key,
                approved   = 1
            """,
            (sym, now, sec_type, exch, ccy, market_key),
        )
    conn.commit()


def init_db():
    conn = get_connection()
    try:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                strength TEXT NOT NULL,
                rsi REAL, macd REAL, volume_ratio REAL,
                extra_indicators TEXT DEFAULT '{}',
                created_at TEXT NOT NULL,
                processed INTEGER DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL, action TEXT NOT NULL,
                quantity INTEGER NOT NULL, entry_price REAL NOT NULL,
                stop_loss_price REAL NOT NULL, take_profit_price REAL NOT NULL,
                stop_loss_pct REAL NOT NULL, take_profit_pct REAL NOT NULL,
                signal_strength TEXT NOT NULL, llm_justification TEXT,
                status TEXT NOT NULL DEFAULT 'OPEN',
                exit_price REAL, exit_reason TEXT,
                pnl_usd REAL, pnl_pct REAL,
                opened_at TEXT NOT NULL, closed_at TEXT, order_id TEXT
            );
            CREATE TABLE IF NOT EXISTS patterns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL, pattern_text TEXT NOT NULL,
                win_count INTEGER DEFAULT 0, loss_count INTEGER DEFAULT 0,
                created_at TEXT NOT NULL, updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS symbol_config (
                symbol TEXT PRIMARY KEY,
                extra_indicators TEXT DEFAULT '[]',
                approved INTEGER DEFAULT 1,
                proposed_by TEXT DEFAULT 'human',
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS decisions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                signal_id INTEGER, symbol TEXT NOT NULL,
                llm_model TEXT NOT NULL, prompt_summary TEXT, response TEXT,
                action TEXT NOT NULL, stop_loss_pct REAL, take_profit_pct REAL,
                created_at TEXT NOT NULL
            );
        """)
        _migrate_symbol_config(conn)
        _seed_symbol_universe(conn)
    finally:
        conn.close()
    init_analysis_tables()
    init_alerts_table()
    init_market_permissions_table()
    init_active_symbols_table()




# --- active_symbols table ---

ACTIVE_SYMBOLS_DDL = """
CREATE TABLE IF NOT EXISTS active_symbols (
    symbol       TEXT NOT NULL,
    market_key   TEXT NOT NULL,
    score        REAL DEFAULT 0.0,
    selected_at  TEXT NOT NULL,
    session_date TEXT NOT NULL,
    PRIMARY KEY (symbol, market_key, session_date)
);
"""


def init_active_symbols_table(conn=None) -> None:
    """Create active_symbols table if it does not exist."""
    _conn = conn or get_connection()
    _conn.execute(ACTIVE_SYMBOLS_DDL)
    _conn.commit()


def upsert_active_symbols(
    market_key: str,
    symbols: list,
    session_date: str,
    scores=None,
    conn=None,
) -> None:
    from datetime import datetime, timezone
    _conn = conn or get_connection()
    selected_at = datetime.now(timezone.utc).isoformat()
    _scores = scores or {}
    _conn.executemany(
        """
        INSERT OR REPLACE INTO active_symbols
            (symbol, market_key, score, selected_at, session_date)
        VALUES (?, ?, ?, ?, ?)
        """,
        [
            (sym, market_key, _scores.get(sym, 0.0), selected_at, session_date)
            for sym in symbols
        ],
    )
    _conn.commit()


def get_active_symbols(
    market_key: str,
    session_date: str,
    conn=None,
) -> list:
    _conn = conn or get_connection()
    cursor = _conn.execute(
        """
        SELECT symbol FROM active_symbols
        WHERE market_key = ? AND session_date = ?
        ORDER BY score DESC
        """,
        (market_key, session_date),
    )
    return [row[0] for row in cursor.fetchall()]


def get_all_active_symbols_today(
    session_date: str,
    conn=None,
) -> list:
    """Return all active symbols for the given session_date, enriched with symbol_config.
    
    NOTE: symbol_config has PRIMARY KEY (symbol) only, so the JOIN uses only a.symbol = s.symbol.
    """
    _conn = conn or get_connection()
    cursor = _conn.execute(
        """
        SELECT
            a.symbol,
            a.market_key,
            a.score,
            s.sec_type,
            s.exchange,
            s.currency,
            s.liquid_hours
        FROM active_symbols a
        LEFT JOIN symbol_config s
            ON a.symbol = s.symbol
        WHERE a.session_date = ?
        ORDER BY a.market_key, a.score DESC
        """,
        (session_date,),
    )
    columns = [col[0] for col in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]

def get_approved_symbols_with_meta() -> list[dict]:
    """Return approved symbols with full multi-market metadata."""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT symbol, sec_type, exchange, currency, liquid_hours, market_key "
            "FROM symbol_config WHERE approved=1"
        ).fetchall()
    finally:
        conn.close()
    return [
        {
            "symbol": r["symbol"],
            "sec_type": r["sec_type"] or "STK",
            "exchange": r["exchange"] or "SMART",
            "currency": r["currency"] or "USD",
            "liquid_hours": r["liquid_hours"],
            "market_key": r["market_key"] or "STK_US",
        }
        for r in rows
    ]


def insert_signal(signal: Signal) -> int:
    conn = get_connection()
    cur = conn.execute(
        "INSERT INTO signals (symbol,strength,rsi,macd,volume_ratio,extra_indicators,created_at) VALUES (?,?,?,?,?,?,?)",
        (signal.symbol, signal.strength, signal.rsi, signal.macd,
         signal.volume_ratio, signal.extra_indicators, signal.created_at.isoformat())
    )
    conn.commit()
    row_id = cur.lastrowid
    conn.close()
    return row_id


def get_pending_signals() -> list:
    conn = get_connection()
    rows = conn.execute("SELECT * FROM signals WHERE processed=0 ORDER BY created_at ASC").fetchall()
    conn.close()
    return [Signal(
        id=r["id"], symbol=r["symbol"], strength=r["strength"],
        rsi=r["rsi"], macd=r["macd"], volume_ratio=r["volume_ratio"],
        extra_indicators=r["extra_indicators"],
        created_at=datetime.fromisoformat(r["created_at"]),
        processed=bool(r["processed"]),
    ) for r in rows]


def mark_signal_processed(signal_id: int):
    conn = get_connection()
    conn.execute("UPDATE signals SET processed=1 WHERE id=?", (signal_id,))
    conn.commit()
    conn.close()


def insert_trade(trade: Trade) -> int:
    conn = get_connection()
    cur = conn.execute(
        """INSERT INTO trades
           (symbol,action,quantity,entry_price,stop_loss_price,take_profit_price,
            stop_loss_pct,take_profit_pct,signal_strength,llm_justification,status,opened_at,order_id)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (trade.symbol, trade.action, trade.quantity, trade.entry_price,
         trade.stop_loss_price, trade.take_profit_price, trade.stop_loss_pct,
         trade.take_profit_pct, trade.signal_strength, trade.llm_justification,
         trade.status, trade.opened_at.isoformat(), trade.order_id)
    )
    conn.commit()
    row_id = cur.lastrowid
    conn.close()
    return row_id


def get_open_trades() -> list:
    conn = get_connection()
    rows = conn.execute("SELECT * FROM trades WHERE status='OPEN'").fetchall()
    conn.close()
    return [Trade(
        id=r["id"], symbol=r["symbol"], action=r["action"],
        quantity=r["quantity"], entry_price=r["entry_price"],
        stop_loss_price=r["stop_loss_price"], take_profit_price=r["take_profit_price"],
        stop_loss_pct=r["stop_loss_pct"], take_profit_pct=r["take_profit_pct"],
        signal_strength=r["signal_strength"], llm_justification=r["llm_justification"],
        status=r["status"], exit_price=r["exit_price"], exit_reason=r["exit_reason"],
        pnl_usd=r["pnl_usd"], pnl_pct=r["pnl_pct"],
        opened_at=datetime.fromisoformat(r["opened_at"]),
        closed_at=datetime.fromisoformat(r["closed_at"]) if r["closed_at"] else None,
        order_id=r["order_id"],
    ) for r in rows]


def close_trade(trade_id: int, exit_price: float, exit_reason: str, pnl_usd: float, pnl_pct: float):
    conn = get_connection()
    conn.execute(
        "UPDATE trades SET status='CLOSED',exit_price=?,exit_reason=?,pnl_usd=?,pnl_pct=?,closed_at=? WHERE id=?",
        (exit_price, exit_reason, pnl_usd, pnl_pct, datetime.utcnow().isoformat(), trade_id)
    )
    conn.commit()
    conn.close()


def get_patterns_for_symbol(symbol: str) -> list:
    conn = get_connection()
    rows = conn.execute("SELECT * FROM patterns WHERE symbol=? ORDER BY win_count DESC", (symbol,)).fetchall()
    conn.close()
    return [Pattern(
        id=r["id"], symbol=r["symbol"], pattern_text=r["pattern_text"],
        win_count=r["win_count"], loss_count=r["loss_count"],
        created_at=datetime.fromisoformat(r["created_at"]),
        updated_at=datetime.fromisoformat(r["updated_at"]),
    ) for r in rows]


def insert_pattern(pattern: Pattern) -> int:
    conn = get_connection()
    cur = conn.execute(
        "INSERT INTO patterns (symbol,pattern_text,win_count,loss_count,created_at,updated_at) VALUES (?,?,?,?,?,?)",
        (pattern.symbol, pattern.pattern_text, pattern.win_count, pattern.loss_count,
         pattern.created_at.isoformat(), pattern.updated_at.isoformat())
    )
    conn.commit()
    row_id = cur.lastrowid
    conn.close()
    return row_id


def get_approved_symbols() -> list:
    conn = get_connection()
    rows = conn.execute("SELECT symbol FROM symbol_config WHERE approved=1").fetchall()
    conn.close()
    return [r["symbol"] for r in rows]


def insert_decision(decision: Decision) -> int:
    conn = get_connection()
    cur = conn.execute(
        """INSERT INTO decisions
           (signal_id,symbol,llm_model,prompt_summary,response,action,stop_loss_pct,take_profit_pct,created_at)
           VALUES (?,?,?,?,?,?,?,?,?)""",
        (decision.signal_id, decision.symbol, decision.llm_model,
         decision.prompt_summary, decision.response, decision.action,
         decision.stop_loss_pct, decision.take_profit_pct, decision.created_at.isoformat())
    )
    conn.commit()
    row_id = cur.lastrowid
    conn.close()
    return row_id


def save_symbol_proposal(symbol: str, reason: str):
    """Guarda un simbolo propuesto pendiente de aprobacion."""
    conn = get_connection()
    now = datetime.utcnow().isoformat()
    conn.execute(
        "INSERT OR IGNORE INTO symbol_config (symbol, approved, proposed_by, created_at) VALUES (?,0,'llm',?)",
        (symbol.upper(), now)
    )
    conn.execute(
        """INSERT INTO decisions
           (signal_id,symbol,llm_model,prompt_summary,response,action,stop_loss_pct,take_profit_pct,created_at)
           VALUES (?,?,?,?,?,?,?,?,?)""",
        (None, symbol.upper(), "human", f"Proposal: {reason}", reason, "PROPOSE", 0, 0, now)
    )
    conn.commit()
    conn.close()


def approve_symbol(symbol: str):
    """Aprueba un simbolo propuesto para que el scanner lo incluya."""
    conn = get_connection()
    conn.execute("UPDATE symbol_config SET approved=1 WHERE symbol=?", (symbol.upper(),))
    conn.commit()
    conn.close()


def get_pending_proposals() -> list:
    """Retorna simbolos propuestos pendientes de aprobacion."""
    conn = get_connection()
    rows = conn.execute("SELECT symbol, proposed_by, created_at FROM symbol_config WHERE approved=0").fetchall()
    conn.close()
    return [{"symbol": r["symbol"], "proposed_by": r["proposed_by"], "created_at": r["created_at"]} for r in rows]


def get_closed_trades(limit: int = 10) -> list:
    """Retorna los ultimos N trades cerrados."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM trades WHERE status='CLOSED' ORDER BY closed_at DESC LIMIT ?",
        (limit,)
    ).fetchall()
    conn.close()
    return [Trade(
        id=r["id"], symbol=r["symbol"], action=r["action"],
        quantity=r["quantity"], entry_price=r["entry_price"],
        stop_loss_price=r["stop_loss_price"], take_profit_price=r["take_profit_price"],
        stop_loss_pct=r["stop_loss_pct"], take_profit_pct=r["take_profit_pct"],
        signal_strength=r["signal_strength"], llm_justification=r["llm_justification"],
        status=r["status"], exit_price=r["exit_price"], exit_reason=r["exit_reason"],
        pnl_usd=r["pnl_usd"], pnl_pct=r["pnl_pct"],
        opened_at=datetime.fromisoformat(r["opened_at"]),
        closed_at=datetime.fromisoformat(r["closed_at"]) if r["closed_at"] else None,
        order_id=r["order_id"],
    ) for r in rows]


def get_daily_pnl() -> float:
    """Retorna el P&L total de trades cerrados hoy."""
    conn = get_connection()
    today = datetime.utcnow().date().isoformat()
    rows = conn.execute(
        "SELECT COALESCE(SUM(pnl_usd), 0) as total FROM trades WHERE status='CLOSED' AND closed_at >= ?",
        (today,)
    ).fetchone()
    conn.close()
    return float(rows["total"])


# --- Alerts CRUD ---

def init_alerts_table():
    """Crea la tabla alerts si no existe."""
    conn = get_connection()
    conn.execute(
        """CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            threshold_pct REAL NOT NULL,
            created_at TEXT NOT NULL,
            triggered_at TEXT
        )"""
    )
    conn.commit()
    conn.close()


def insert_alert(symbol: str, threshold_pct: float) -> int:
    conn = get_connection()
    cur = conn.execute(
        "INSERT INTO alerts (symbol, threshold_pct, created_at) VALUES (?,?,?)",
        (symbol.upper(), threshold_pct, datetime.utcnow().isoformat())
    )
    conn.commit()
    row_id = cur.lastrowid
    conn.close()
    return row_id


def get_active_alerts() -> list:
    from app.alerts.manager import AlertConfig
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM alerts WHERE triggered_at IS NULL ORDER BY created_at ASC"
    ).fetchall()
    conn.close()
    return [AlertConfig(id=r["id"], symbol=r["symbol"], threshold_pct=r["threshold_pct"]) for r in rows]


def mark_alert_triggered(alert_id: int):
    conn = get_connection()
    conn.execute(
        "UPDATE alerts SET triggered_at=? WHERE id=?",
        (datetime.utcnow().isoformat(), alert_id)
    )
    conn.commit()
    conn.close()


def delete_alert(alert_id: int):
    conn = get_connection()
    conn.execute("DELETE FROM alerts WHERE id=?", (alert_id,))
    conn.commit()
    conn.close()


def get_all_alerts() -> list:
    from app.alerts.manager import AlertConfig
    conn = get_connection()
    rows = conn.execute("SELECT * FROM alerts ORDER BY created_at DESC").fetchall()
    conn.close()
    return [AlertConfig(id=r["id"], symbol=r["symbol"], threshold_pct=r["threshold_pct"]) for r in rows]


def get_patterns_for_week(since: datetime) -> list:
    """Retorna patrones creados desde una fecha."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM patterns WHERE created_at >= ? ORDER BY created_at DESC",
        (since.isoformat(),)
    ).fetchall()
    conn.close()
    return [Pattern(
        id=r["id"], symbol=r["symbol"], pattern_text=r["pattern_text"],
        win_count=r["win_count"], loss_count=r["loss_count"],
        created_at=datetime.fromisoformat(r["created_at"]),
        updated_at=datetime.fromisoformat(r["updated_at"]),
    ) for r in rows]


# --- Analysis tables ---

def init_analysis_tables():
    conn = get_connection()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS feature_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL, timestamp TEXT NOT NULL, context TEXT NOT NULL,
            rsi_14 REAL, macd_line REAL, macd_signal REAL, macd_crossover INTEGER,
            atr_pct REAL, sma20 REAL, sma50 REAL, sma200 REAL,
            bollinger_upper REAL, bollinger_lower REAL, bollinger_position REAL,
            vwap REAL, volume_ratio_20d REAL, hist_volatility_30d REAL,
            impl_volatility REAL, rs_vs_spy_30d REAL, rs_vs_qqq_30d REAL,
            feature_relevance_json TEXT DEFAULT '{}'
        );
        CREATE TABLE IF NOT EXISTS symbol_parameters (
            symbol TEXT PRIMARY KEY,
            stop_loss_pct REAL DEFAULT 0.025, take_profit_pct REAL DEFAULT 0.06,
            min_profit_pct REAL DEFAULT 0.01,
            momentum_mult REAL DEFAULT 1.0, trend_mult REAL DEFAULT 1.0,
            volume_mult REAL DEFAULT 1.0, volatility_mult REAL DEFAULT 1.0,
            portfolio_fit_mult REAL DEFAULT 1.0, sentiment_mult REAL DEFAULT 1.0,
            trade_count INTEGER DEFAULT 0, version INTEGER DEFAULT 1,
            previous_json TEXT, updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS candidate_decisions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL, decision_date TEXT NOT NULL, decision TEXT NOT NULL,
            price_at_decision REAL, quant_score REAL, feature_snapshot_id INTEGER,
            llm_summary TEXT, future_return_7d REAL, future_return_30d REAL,
            alpha_vs_spy_7d REAL, alpha_vs_spy_30d REAL,
            evaluated_7d_at TEXT, evaluated_30d_at TEXT
        );
        CREATE TABLE IF NOT EXISTS watchlist_scores (
            symbol TEXT PRIMARY KEY,
            signal_quality_score REAL DEFAULT 0.5, admission_score REAL DEFAULT 0.5,
            trade_history_score REAL DEFAULT 0.5, watchlist_score REAL DEFAULT 0.5,
            last_updated TEXT NOT NULL
        );
    """)
    conn.commit()
    conn.close()


def insert_feature_snapshot(fs_dict: dict) -> int:
    conn = get_connection()
    cur = conn.execute(
        """INSERT INTO feature_snapshots
           (symbol,timestamp,context,rsi_14,macd_line,macd_signal,macd_crossover,
            atr_pct,sma20,sma50,sma200,bollinger_upper,bollinger_lower,bollinger_position,
            vwap,volume_ratio_20d,hist_volatility_30d,impl_volatility,rs_vs_spy_30d,
            rs_vs_qqq_30d,feature_relevance_json)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (fs_dict.get("symbol"), fs_dict.get("timestamp"), fs_dict.get("context", "unknown"),
         fs_dict.get("rsi_14"), fs_dict.get("macd_line"), fs_dict.get("macd_signal"),
         int(fs_dict["macd_crossover"]) if fs_dict.get("macd_crossover") is not None else None,
         fs_dict.get("atr_pct"), fs_dict.get("sma20"), fs_dict.get("sma50"), fs_dict.get("sma200"),
         fs_dict.get("bollinger_upper"), fs_dict.get("bollinger_lower"), fs_dict.get("bollinger_position"),
         fs_dict.get("vwap"), fs_dict.get("volume_ratio_20d"), fs_dict.get("hist_volatility_30d"),
         fs_dict.get("impl_volatility"), fs_dict.get("rs_vs_spy_30d"), fs_dict.get("rs_vs_qqq_30d"),
         str(fs_dict.get("feature_relevance", "{}")))
    )
    conn.commit()
    row_id = cur.lastrowid
    conn.close()
    return row_id


def insert_candidate_decision(symbol: str, decision: str, price: float, score: float,
                               feature_snapshot_id: int = None, llm_summary: str = None) -> int:
    conn = get_connection()
    cur = conn.execute(
        """INSERT INTO candidate_decisions
           (symbol, decision_date, decision, price_at_decision, quant_score,
            feature_snapshot_id, llm_summary)
           VALUES (?,?,?,?,?,?,?)""",
        (symbol, datetime.utcnow().isoformat(), decision, price, score,
         feature_snapshot_id, llm_summary)
    )
    conn.commit()
    row_id = cur.lastrowid
    conn.close()
    return row_id


def get_candidate_decisions_for_evaluation(days_ago: int) -> list:
    from app.db.models import CandidateDecision
    conn = get_connection()
    cutoff = (datetime.utcnow() - __import__("datetime").timedelta(days=days_ago + 1)).isoformat()
    end = (datetime.utcnow() - __import__("datetime").timedelta(days=days_ago - 1)).isoformat()
    field = "future_return_7d" if days_ago <= 10 else "future_return_30d"
    rows = conn.execute(
        f"SELECT * FROM candidate_decisions WHERE {field} IS NULL AND decision_date BETWEEN ? AND ?",
        (cutoff, end)
    ).fetchall()
    conn.close()
    return [CandidateDecision(
        id=r["id"], symbol=r["symbol"], decision_date=r["decision_date"],
        decision=r["decision"], price_at_decision=r["price_at_decision"],
        quant_score=r["quant_score"], feature_snapshot_id=r["feature_snapshot_id"],
        llm_summary=r["llm_summary"],
    ) for r in rows]


def get_or_create_symbol_parameters(symbol: str):
    from app.db.models import SymbolParameter
    conn = get_connection()
    row = conn.execute("SELECT * FROM symbol_parameters WHERE symbol=?", (symbol.upper(),)).fetchone()
    conn.close()
    if row:
        return SymbolParameter(
            symbol=row["symbol"], stop_loss_pct=row["stop_loss_pct"],
            take_profit_pct=row["take_profit_pct"], min_profit_pct=row["min_profit_pct"],
            momentum_mult=row["momentum_mult"], trend_mult=row["trend_mult"],
            volume_mult=row["volume_mult"], volatility_mult=row["volatility_mult"],
            portfolio_fit_mult=row["portfolio_fit_mult"], sentiment_mult=row["sentiment_mult"],
            trade_count=row["trade_count"], version=row["version"],
            previous_json=row["previous_json"], updated_at=row["updated_at"],
        )
    # Create default
    conn = get_connection()
    now = datetime.utcnow().isoformat()
    conn.execute(
        """INSERT OR IGNORE INTO symbol_parameters
           (symbol, updated_at) VALUES (?,?)""",
        (symbol.upper(), now)
    )
    conn.commit()
    conn.close()
    return SymbolParameter(symbol=symbol.upper(), updated_at=now)


def update_symbol_parameters(symbol: str, **kwargs):
    conn = get_connection()
    kwargs["updated_at"] = datetime.utcnow().isoformat()
    sets = ", ".join(f"{k}=?" for k in kwargs)
    vals = list(kwargs.values()) + [symbol.upper()]
    conn.execute(f"UPDATE symbol_parameters SET {sets} WHERE symbol=?", vals)
    conn.commit()
    conn.close()


def upsert_watchlist_score(symbol: str, **scores):
    conn = get_connection()
    now = datetime.utcnow().isoformat()
    scores["last_updated"] = now
    fields = list(scores.keys())
    vals = list(scores.values())
    placeholders = ",".join(["?"] * (len(fields) + 1))
    field_names = "symbol," + ",".join(fields)
    update_set = ",".join(f"{f}=excluded.{f}" for f in fields)
    conn.execute(
        f"INSERT INTO watchlist_scores ({field_names}) VALUES ({placeholders}) "
        f"ON CONFLICT(symbol) DO UPDATE SET {update_set}",
        [symbol.upper()] + vals
    )
    conn.commit()
    conn.close()


# --- Market permissions table ---

def init_market_permissions_table():
    conn = get_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS market_permissions (
            key TEXT PRIMARY KEY,
            label TEXT NOT NULL,
            sec_type TEXT NOT NULL,
            available INTEGER NOT NULL DEFAULT 0,
            valid_exchanges TEXT DEFAULT '',
            checked_at TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()


def upsert_market_permissions(results: list):
    conn = get_connection()
    for r in results:
        conn.execute(
            """INSERT INTO market_permissions (key, label, sec_type, available, valid_exchanges, checked_at)
               VALUES (?,?,?,?,?,?)
               ON CONFLICT(key) DO UPDATE SET
                 label=excluded.label, sec_type=excluded.sec_type,
                 available=excluded.available, valid_exchanges=excluded.valid_exchanges,
                 checked_at=excluded.checked_at""",
            (r["key"], r["label"], r["sec_type"],
             1 if r["available"] else 0, r.get("valid_exchanges", ""), r["checked_at"])
        )
    conn.commit()
    conn.close()


def get_market_permissions() -> list:
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM market_permissions ORDER BY key"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_market_permissions_age_hours() -> float | None:
    conn = get_connection()
    row = conn.execute(
        "SELECT checked_at FROM market_permissions ORDER BY checked_at DESC LIMIT 1"
    ).fetchone()
    conn.close()
    if not row:
        return None
    from datetime import timezone
    last = datetime.fromisoformat(row["checked_at"])
    now = datetime.utcnow()
    return (now - last).total_seconds() / 3600
