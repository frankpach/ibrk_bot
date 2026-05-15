# app/infrastructure/db/compat.py
"""Compatibility layer — re-exports all legacy database functions using SQLAlchemy."""
import sqlite3
import json
import logging
from datetime import datetime
from app.db.models import Signal, Trade, Pattern, Decision

logger = logging.getLogger(__name__)


def get_connection():
    """Return a raw sqlite3 connection (direct, independent of SQLAlchemy pool)."""
    from app.config.settings import DB_PATH
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
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


def _migrate_trades_state_machine(conn) -> None:
    """Migrate trades table for state machine + fill tracking."""
    _add_column_if_missing(conn, "trades", "trade_status", "TEXT DEFAULT 'PENDING'")
    _add_column_if_missing(conn, "trades", "entry_fill_price", "REAL")
    _add_column_if_missing(conn, "trades", "exit_fill_price", "REAL")
    _add_column_if_missing(conn, "trades", "close_order_id", "TEXT")
    _add_column_if_missing(conn, "trades", "partial_exit_done", "INTEGER DEFAULT 0")
    _add_column_if_missing(conn, "trades", "remaining_quantity", "REAL")
    # Backfill: existing OPEN trades -> trade_status='OPEN', CLOSED -> 'CLOSED'
    try:
        conn.execute("UPDATE trades SET trade_status='OPEN' WHERE status='OPEN' AND (trade_status IS NULL OR trade_status='PENDING')")
        conn.execute("UPDATE trades SET trade_status='CLOSED' WHERE status='CLOSED' AND (trade_status IS NULL OR trade_status='PENDING')")
        conn.commit()
    except Exception:
        pass


def _migrate_audit_log(conn) -> None:
    """Migrate audit_log table to the new schema (old_value, new_value, changed_by, ip_address, occurred_at)."""
    try:
        # Check if the old schema exists by probing the 'symbol' column
        cursor = conn.execute("PRAGMA table_info(audit_log)")
        columns = {row[1] for row in cursor.fetchall()}
        if "symbol" not in columns:
            # Already migrated or created with new schema
            return

        # Rename old table, create new, migrate data
        conn.execute("ALTER TABLE audit_log RENAME TO audit_log_old")
        conn.execute("""
            CREATE TABLE audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT NOT NULL,
                entity_type TEXT,
                entity_id INTEGER,
                old_value TEXT,
                new_value TEXT,
                changed_by TEXT,
                ip_address TEXT,
                occurred_at TEXT NOT NULL
            )
        """)
        conn.execute("""
            INSERT INTO audit_log (id, event_type, entity_type, entity_id, old_value, new_value, changed_by, occurred_at)
            SELECT id, event_type, entity_type, entity_id, NULL, details, NULL, created_at FROM audit_log_old
        """)
        conn.execute("DROP TABLE audit_log_old")
        conn.commit()
    except Exception as exc:
        logger.warning(f"audit_log migration skipped or failed: {exc}")


def _migrate_control_settings(conn) -> None:
    """Add is_secret, requires_restart, updated_by columns to control_settings."""
    _add_column_if_missing(conn, "control_settings", "is_secret", "INTEGER DEFAULT 0")
    _add_column_if_missing(conn, "control_settings", "requires_restart", "INTEGER DEFAULT 0")
    _add_column_if_missing(conn, "control_settings", "updated_by", "TEXT")


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
                quantity REAL NOT NULL, entry_price REAL NOT NULL,
                stop_loss_price REAL NOT NULL, take_profit_price REAL NOT NULL,
                stop_loss_pct REAL NOT NULL, take_profit_pct REAL NOT NULL,
                signal_strength TEXT NOT NULL, llm_justification TEXT,
                status TEXT NOT NULL DEFAULT 'OPEN',
                exit_price REAL, exit_reason TEXT,
                pnl_usd REAL, pnl_pct REAL,
                opened_at TEXT NOT NULL, closed_at TEXT, order_id TEXT,
                trade_status TEXT DEFAULT 'PENDING',
                entry_fill_price REAL, exit_fill_price REAL,
                close_order_id TEXT,
                partial_exit_done INTEGER DEFAULT 0,
                remaining_quantity REAL
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
            CREATE TABLE IF NOT EXISTS audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT NOT NULL,
                entity_type TEXT,
                entity_id INTEGER,
                old_value TEXT,
                new_value TEXT,
                changed_by TEXT,
                ip_address TEXT,
                occurred_at TEXT NOT NULL
            );
            CREATE UNIQUE INDEX IF NOT EXISTS idx_open_symbol ON trades(symbol) WHERE status='OPEN';
            CREATE INDEX IF NOT EXISTS idx_audit_log_type ON audit_log(event_type, occurred_at);

            CREATE TABLE IF NOT EXISTS control_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS background_jobs (
                job_id TEXT PRIMARY KEY,
                job_type TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                params TEXT,
                result TEXT,
                error TEXT,
                created_at TEXT NOT NULL,
                started_at TEXT,
                completed_at TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_bgjobs_type ON background_jobs(job_type, status, created_at);
        """)
        _migrate_symbol_config(conn)
        _migrate_trades_state_machine(conn)
        _migrate_audit_log(conn)
        _migrate_control_settings(conn)
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


def get_pending_signals(since_hours: int = None) -> list:
    conn = get_connection()
    sql = "SELECT * FROM signals WHERE processed=0"
    params = []
    if since_hours is not None:
        from datetime import timezone
        cutoff = (datetime.now(timezone.utc) - __import__("datetime").timedelta(hours=since_hours)).isoformat()
        sql += " AND created_at >= ?"
        params.append(cutoff)
    sql += " ORDER BY created_at ASC"
    rows = conn.execute(sql, params).fetchall()
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
            stop_loss_pct,take_profit_pct,signal_strength,llm_justification,status,opened_at,order_id,
            trade_status,entry_fill_price,exit_fill_price,close_order_id,partial_exit_done,remaining_quantity)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (trade.symbol, trade.action, trade.quantity, trade.entry_price,
         trade.stop_loss_price, trade.take_profit_price, trade.stop_loss_pct,
         trade.take_profit_pct, trade.signal_strength, trade.llm_justification,
         trade.status, trade.opened_at.isoformat(), trade.order_id,
         trade.trade_status, trade.entry_fill_price, trade.exit_fill_price,
         trade.close_order_id, int(trade.partial_exit_done), trade.remaining_quantity)
    )
    conn.commit()
    row_id = cur.lastrowid
    conn.close()
    return row_id


def _row_to_trade(r) -> Trade:
    """Convert a DB row to Trade dataclass."""
    return Trade(
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
        trade_status=r["trade_status"] or "PENDING",
        entry_fill_price=r["entry_fill_price"],
        exit_fill_price=r["exit_fill_price"],
        close_order_id=r["close_order_id"],
        partial_exit_done=bool(r["partial_exit_done"]),
        remaining_quantity=r["remaining_quantity"],
    )


def get_open_trades() -> list:
    conn = get_connection()
    rows = conn.execute("SELECT * FROM trades WHERE status='OPEN'").fetchall()
    conn.close()
    return [_row_to_trade(r) for r in rows]


def get_trades_by_status(trade_status: str) -> list:
    """Get trades by trade_status (state machine)."""
    conn = get_connection()
    rows = conn.execute("SELECT * FROM trades WHERE trade_status=?", (trade_status,)).fetchall()
    conn.close()
    return [_row_to_trade(r) for r in rows]


def update_trade_status(trade_id: int, trade_status: str = None, order_id: str = None, fill_price: float = None, stop_loss_price: float = None, remaining_quantity: float = None):
    """Update trade status and optionally fill price / order_id / stop_loss / remaining_quantity."""
    conn = get_connection()
    fields = []
    params = []
    if trade_status is not None:
        fields.append("trade_status=?")
        params.append(trade_status)
    if order_id is not None:
        fields.append("order_id=COALESCE(?,order_id)")
        params.append(order_id)
    if fill_price is not None:
        fields.append("entry_fill_price=COALESCE(?,entry_fill_price)")
        params.append(fill_price)
    if stop_loss_price is not None:
        fields.append("stop_loss_price=?")
        params.append(stop_loss_price)
    if remaining_quantity is not None:
        fields.append("remaining_quantity=?")
        params.append(remaining_quantity)
    if not fields:
        conn.close()
        return
    params.append(trade_id)
    sql = f"UPDATE trades SET {','.join(fields)} WHERE id=?"
    conn.execute(sql, params)
    conn.commit()
    conn.close()


def update_trade_close_fill(trade_id: int, close_order_id: str, exit_fill_price: float):
    """Update close order ID and exit fill price."""
    conn = get_connection()
    conn.execute(
        "UPDATE trades SET close_order_id=?, exit_fill_price=? WHERE id=?",
        (close_order_id, exit_fill_price, trade_id)
    )
    conn.commit()
    conn.close()


def close_trade(trade_id: int, exit_price: float, exit_reason: str, pnl_usd: float, pnl_pct: float, exit_fill_price: float = None):
    conn = get_connection()
    conn.execute(
        "UPDATE trades SET status='CLOSED',trade_status='CLOSED',exit_price=?,exit_fill_price=?,exit_reason=?,pnl_usd=?,pnl_pct=?,closed_at=? WHERE id=?",
        (exit_price, exit_fill_price, exit_reason, pnl_usd, pnl_pct, datetime.utcnow().isoformat(), trade_id)
    )
    conn.commit()
    conn.close()


def get_closed_trades_by_symbol(symbol: str, limit: int = 10) -> list:
    """Return most recent closed trades for a symbol, newest first."""
    conn = get_connection()
    rows = conn.execute(
        """SELECT * FROM trades
           WHERE symbol=? AND status='CLOSED'
           ORDER BY closed_at DESC
           LIMIT ?""",
        (symbol.upper(), limit)
    ).fetchall()
    conn.close()
    result = []
    for r in rows:
        keys = [col[0] for col in conn.description] if hasattr(conn, 'description') else list(r.keys())
        result.append(Trade(
            id=r["id"], symbol=r["symbol"], action=r["action"],
            quantity=r["quantity"], entry_price=r["entry_price"],
            stop_loss_price=r["stop_loss_price"],
            take_profit_price=r["take_profit_price"],
            stop_loss_pct=r["stop_loss_pct"],
            take_profit_pct=r["take_profit_pct"],
            signal_strength=r["signal_strength"],
            llm_justification=r["llm_justification"],
            status=r["status"],
            exit_price=r["exit_price"],
            exit_reason=r["exit_reason"],
            pnl_usd=r["pnl_usd"],
            pnl_pct=r["pnl_pct"],
            opened_at=datetime.fromisoformat(r["opened_at"]),
            closed_at=datetime.fromisoformat(r["closed_at"]) if r["closed_at"] else None,
            order_id=r["order_id"] if "order_id" in r.keys() else None,
            trade_status=r["trade_status"] if "trade_status" in r.keys() else "PENDING",
            entry_fill_price=r["entry_fill_price"] if "entry_fill_price" in r.keys() else None,
            exit_fill_price=r["exit_fill_price"] if "exit_fill_price" in r.keys() else None,
            close_order_id=r["close_order_id"] if "close_order_id" in r.keys() else None,
            partial_exit_done=bool(r["partial_exit_done"]) if "partial_exit_done" in r.keys() else False,
            remaining_quantity=r["remaining_quantity"] if "remaining_quantity" in r.keys() else None,
        ))
    return result


def get_patterns_for_symbol(symbol: str, limit: int = None) -> list:
    conn = get_connection()
    if limit is None:
        rows = conn.execute("SELECT * FROM patterns WHERE symbol=? ORDER BY updated_at DESC", (symbol,)).fetchall()
    else:
        rows = conn.execute("SELECT * FROM patterns WHERE symbol=? ORDER BY updated_at DESC LIMIT ?", (symbol, limit)).fetchall()
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


def approve_symbol(symbol: str, ib_client=None) -> None:
    """Aprueba un simbolo — inserta en symbol_config si no existe, luego lo activa."""
    sym = symbol.upper()
    conn = get_connection()
    # Insert if not already in symbol_config (handles symbols outside the seed)
    conn.execute(
        """INSERT OR IGNORE INTO symbol_config
           (symbol, extra_indicators, approved, proposed_by, created_at,
            sec_type, exchange, currency, market_key)
           VALUES (?, '[]', 0, 'dashboard', ?, 'STK', 'SMART', 'USD', 'STK_US')""",
        (sym, datetime.utcnow().isoformat())
    )
    conn.execute("UPDATE symbol_config SET approved=1 WHERE symbol=?", (sym,))
    conn.commit()
    conn.close()
    # Trigger background calibration if IB client available
    if ib_client is not None:
        try:
            from app.ml.calibration import on_symbol_approved
            on_symbol_approved(symbol.upper(), ib_client)
        except Exception as e:
            logger.warning(f"Calibration hook failed for {symbol}: {e}")


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
    """Retorna el P&L total de trades cerrados hoy (horario ET)."""
    from app.config.settings import MARKET_TZ
    conn = get_connection()
    today = datetime.now(MARKET_TZ).date().isoformat()
    # Sumar trades cerrados hoy en ET (desde 00:00 ET)
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
        CREATE TABLE IF NOT EXISTS position_snapshots (
            trade_id INTEGER PRIMARY KEY,
            symbol TEXT NOT NULL,
            current_price REAL,
            pnl_usd REAL,
            pnl_pct REAL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS account_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL UNIQUE,
            net_liquidation REAL,
            buying_power REAL,
            daily_pnl_usd REAL,
            daily_pnl_pct REAL,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS news_cache (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT,
            headline TEXT NOT NULL,
            provider TEXT,
            sentiment TEXT,
            article_id TEXT,
            published_at TEXT,
            url TEXT,
            fetched_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS scanner_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scan_type TEXT NOT NULL,
            symbol TEXT NOT NULL,
            name TEXT,
            change_pct REAL,
            volume_ratio REAL,
            extra_json TEXT DEFAULT '{}',
            fetched_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS analysis_reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            report_type TEXT NOT NULL,
            report_date TEXT NOT NULL,
            title TEXT NOT NULL,
            content_md TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_reports_date ON analysis_reports(report_date, report_type);
        CREATE TABLE IF NOT EXISTS daily_watchlist (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            symbol TEXT NOT NULL,
            score REAL,
            signal_strength TEXT,
            change_pct REAL,
            volume_ratio REAL,
            reason TEXT,
            alerted INTEGER DEFAULT 0,
            added_at TEXT NOT NULL,
            UNIQUE(date, symbol)
        );
    """)
    conn.commit()
    _add_column_if_missing(conn, "trades", "feature_snapshot_id", "INTEGER")
    conn.commit()
    # Migrate feature_snapshots for hourly and weekly fields
    _add_column_if_missing(conn, "feature_snapshots", "rsi_1h", "REAL")
    _add_column_if_missing(conn, "feature_snapshots", "volume_ratio_1h", "REAL")
    _add_column_if_missing(conn, "feature_snapshots", "weekly_trend", "TEXT")
    # MTE-010: backtest calibration columns
    _add_column_if_missing(conn, "symbol_parameters", "backtest_calibrated", "INTEGER DEFAULT 0")
    _add_column_if_missing(conn, "symbol_parameters", "backtest_calibrated_at", "TEXT")
    # LD-001: backtest_profit_factor column
    _add_column_if_missing(conn, "symbol_parameters", "backtest_profit_factor", "REAL")
    _add_column_if_missing(conn, "news_cache", "url", "TEXT")
    conn.commit()
    conn.close()


def get_feature_snapshot_by_id(snapshot_id: int) -> dict | None:
    """Return feature snapshot as dict, or None if not found."""
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM feature_snapshots WHERE id=?", (snapshot_id,)
    ).fetchone()
    conn.close()
    if row is None:
        return None
    return dict(row)


def get_closed_trades_with_snapshots(limit: int = 200) -> list:
    """Return closed trades that have a feature_snapshot_id, as dicts with snapshot fields."""
    conn = get_connection()
    rows = conn.execute(
        """SELECT t.id, t.symbol, t.action, t.pnl_pct, t.pnl_usd, t.exit_reason,
                  t.stop_loss_pct, t.take_profit_pct, t.signal_strength,
                  t.feature_snapshot_id,
                  fs.rsi_14, fs.macd_line, fs.atr_pct, fs.volume_ratio_20d,
                  fs.bollinger_position, fs.rs_vs_spy_30d
           FROM trades t
           JOIN feature_snapshots fs ON t.feature_snapshot_id = fs.id
           WHERE t.status = 'CLOSED'
           ORDER BY t.closed_at DESC
           LIMIT ?""",
        (limit,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def insert_feature_snapshot(fs_dict: dict) -> int:
    conn = get_connection()
    cur = conn.execute(
        """INSERT INTO feature_snapshots
           (symbol,timestamp,context,rsi_14,macd_line,macd_signal,macd_crossover,
            atr_pct,sma20,sma50,sma200,bollinger_upper,bollinger_lower,bollinger_position,
            vwap,volume_ratio_20d,hist_volatility_30d,impl_volatility,rs_vs_spy_30d,
            rs_vs_qqq_30d,feature_relevance_json,rsi_1h,volume_ratio_1h,weekly_trend)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (fs_dict.get("symbol"), fs_dict.get("timestamp"), fs_dict.get("context", "unknown"),
         fs_dict.get("rsi_14"), fs_dict.get("macd_line"), fs_dict.get("macd_signal"),
         int(fs_dict["macd_crossover"]) if fs_dict.get("macd_crossover") is not None else None,
         fs_dict.get("atr_pct"), fs_dict.get("sma20"), fs_dict.get("sma50"), fs_dict.get("sma200"),
         fs_dict.get("bollinger_upper"), fs_dict.get("bollinger_lower"), fs_dict.get("bollinger_position"),
         fs_dict.get("vwap"), fs_dict.get("volume_ratio_20d"), fs_dict.get("hist_volatility_30d"),
         fs_dict.get("impl_volatility"), fs_dict.get("rs_vs_spy_30d"), fs_dict.get("rs_vs_qqq_30d"),
         str(fs_dict.get("feature_relevance", "{}")),
         fs_dict.get("rsi_1h"), fs_dict.get("volume_ratio_1h"), fs_dict.get("weekly_trend"))
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
            backtest_calibrated=row["backtest_calibrated"] if "backtest_calibrated" in row.keys() else 0,
            backtest_calibrated_at=row["backtest_calibrated_at"] if "backtest_calibrated_at" in row.keys() else None,
            backtest_profit_factor=row["backtest_profit_factor"] if "backtest_profit_factor" in row.keys() else None,
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
    return SymbolParameter(symbol=symbol.upper(), updated_at=now,
                           backtest_calibrated=0, backtest_calibrated_at=None,
                           backtest_profit_factor=None)


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


# --- LD-001: Live Dashboard CRUD ---

def upsert_position_snapshot(trade_id: int, symbol: str, current_price: float,
                              pnl_usd: float, pnl_pct: float) -> None:
    conn = get_connection()
    conn.execute(
        """INSERT OR REPLACE INTO position_snapshots
           (trade_id, symbol, current_price, pnl_usd, pnl_pct, updated_at)
           VALUES (?,?,?,?,?,?)""",
        (trade_id, symbol, current_price, pnl_usd, pnl_pct, datetime.utcnow().isoformat())
    )
    conn.commit()
    conn.close()


def get_position_snapshots() -> dict:
    """Return {trade_id: {current_price, pnl_usd, pnl_pct, updated_at}}."""
    conn = get_connection()
    rows = conn.execute("SELECT * FROM position_snapshots").fetchall()
    conn.close()
    return {r["trade_id"]: dict(r) for r in rows}


def upsert_account_snapshot(date: str, net_liquidation: float, buying_power: float,
                             daily_pnl_usd: float, daily_pnl_pct: float) -> None:
    conn = get_connection()
    conn.execute(
        """INSERT OR REPLACE INTO account_snapshots
           (date, net_liquidation, buying_power, daily_pnl_usd, daily_pnl_pct, created_at)
           VALUES (?,?,?,?,?,?)""",
        (date, net_liquidation, buying_power, daily_pnl_usd, daily_pnl_pct,
         datetime.utcnow().isoformat())
    )
    conn.commit()
    conn.close()


def get_account_history(days: int = 30) -> list:
    """Return last N days of account snapshots, oldest first."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM account_snapshots ORDER BY date DESC LIMIT ?", (days,)
    ).fetchall()
    conn.close()
    return list(reversed([dict(r) for r in rows]))


def insert_news_cache(symbol: str, headline: str, provider: str, sentiment: str,
                      article_id: str, published_at: str, url: str = "") -> None:
    conn = get_connection()
    conn.execute(
        """INSERT INTO news_cache
           (symbol, headline, provider, sentiment, article_id, published_at, url, fetched_at)
           VALUES (?,?,?,?,?,?,?,?)""",
        (symbol, headline, provider, sentiment, article_id, published_at, url,
         datetime.utcnow().isoformat())
    )
    conn.commit()
    conn.close()


def get_news_cache(symbols: list = None, limit: int = 20) -> list:
    """Return cached news, optionally filtered by symbol list."""
    conn = get_connection()
    if symbols:
        placeholders = ",".join("?" * len(symbols))
        rows = conn.execute(
            f"SELECT * FROM news_cache WHERE symbol IN ({placeholders}) "
            f"ORDER BY fetched_at DESC LIMIT ?",
            list(symbols) + [limit]
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM news_cache ORDER BY fetched_at DESC LIMIT ?", (limit,)
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def clear_news_cache_older_than(hours: int = 24) -> None:
    from datetime import timedelta
    cutoff = (datetime.utcnow() - timedelta(hours=hours)).isoformat()
    conn = get_connection()
    conn.execute("DELETE FROM news_cache WHERE fetched_at < ?", (cutoff,))
    conn.commit()
    conn.close()


def upsert_scanner_results(scan_type: str, results: list) -> None:
    """Replace all results for a scan_type with fresh data."""
    conn = get_connection()
    conn.execute("DELETE FROM scanner_results WHERE scan_type=?", (scan_type,))
    now = datetime.utcnow().isoformat()
    for r in results:
        conn.execute(
            """INSERT INTO scanner_results
               (scan_type, symbol, name, change_pct, volume_ratio, extra_json, fetched_at)
               VALUES (?,?,?,?,?,?,?)""",
            (scan_type, r.get("symbol"), r.get("name"), r.get("change_pct"),
             r.get("volume_ratio"), r.get("extra_json", "{}"), now)
        )
    conn.commit()
    conn.close()


def get_scanner_results(scan_type: str) -> list:
    """Return scanner results for a given scan_type."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM scanner_results WHERE scan_type=? ORDER BY rowid",
        (scan_type,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# --- Analysis Reports CRUD ---

def save_report(report_type: str, report_date: str, title: str, content_md: str) -> int:
    """Save a report. Returns the new report id."""
    conn = get_connection()
    cur = conn.execute(
        """INSERT INTO analysis_reports (report_type, report_date, title, content_md, created_at)
           VALUES (?,?,?,?,?)""",
        (report_type, report_date, title, content_md, datetime.utcnow().isoformat())
    )
    conn.commit()
    row_id = cur.lastrowid
    conn.close()
    # Keep only last 3 days of reports (rolling retention)
    _cleanup_old_reports(days=3)
    return row_id


def get_reports(limit: int = 20) -> list:
    """Return recent reports, newest first."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT id, report_type, report_date, title, created_at FROM analysis_reports ORDER BY created_at DESC LIMIT ?",
        (limit,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_report_by_id(report_id: int) -> dict | None:
    conn = get_connection()
    row = conn.execute("SELECT * FROM analysis_reports WHERE id=?", (report_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def delete_report(report_id: int) -> bool:
    conn = get_connection()
    cur = conn.execute("DELETE FROM analysis_reports WHERE id=?", (report_id,))
    conn.commit()
    conn.close()
    return cur.rowcount > 0


def _cleanup_old_reports(days: int = 3) -> None:
    from datetime import timedelta
    cutoff = (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%d")
    conn = get_connection()
    conn.execute("DELETE FROM analysis_reports WHERE report_date < ?", (cutoff,))
    conn.commit()
    conn.close()


# --- Daily Watchlist CRUD ---

def upsert_daily_watchlist(date: str, symbol: str, score: float, signal_strength: str,
                            change_pct: float, volume_ratio: float, reason: str) -> bool:
    """Add or update a symbol in today's watchlist. Returns True if it's new."""
    conn = get_connection()
    existing = conn.execute(
        "SELECT id FROM daily_watchlist WHERE date=? AND symbol=?", (date, symbol)
    ).fetchone()
    if existing:
        conn.execute(
            """UPDATE daily_watchlist SET score=?, signal_strength=?, change_pct=?,
               volume_ratio=?, reason=? WHERE date=? AND symbol=?""",
            (score, signal_strength, change_pct, volume_ratio, reason, date, symbol)
        )
        conn.commit()
        conn.close()
        return False  # not new
    conn.execute(
        """INSERT INTO daily_watchlist (date, symbol, score, signal_strength,
           change_pct, volume_ratio, reason, alerted, added_at)
           VALUES (?,?,?,?,?,?,?,0,?)""",
        (date, symbol, score, signal_strength, change_pct, volume_ratio, reason,
         datetime.utcnow().isoformat())
    )
    conn.commit()
    conn.close()
    return True  # new entry


def get_daily_watchlist(date: str = None) -> list:
    """Get today's watchlist (or specific date), ordered by score desc."""
    from datetime import datetime as _dt
    target_date = date or _dt.utcnow().strftime("%Y-%m-%d")
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM daily_watchlist WHERE date=? ORDER BY score DESC",
        (target_date,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def mark_watchlist_alerted(symbol: str, date: str) -> None:
    conn = get_connection()
    conn.execute("UPDATE daily_watchlist SET alerted=1 WHERE symbol=? AND date=?", (symbol, date))
    conn.commit()
    conn.close()


# --- control_settings CRUD ---

def init_control_settings() -> None:
    """Bootstrap control_settings from environment if table is empty."""
    import app.config.settings as s
    conn = get_connection()
    try:
        row = conn.execute("SELECT COUNT(*) FROM control_settings").fetchone()
        if row[0] == 0:
            now = datetime.utcnow().isoformat()
            trading_mode = "paper" if s.PAPER_TRADING_ONLY else "live"
            is_paused = "1" if False else "0"
            conn.executemany(
                "INSERT INTO control_settings (key, value, updated_at, is_secret, requires_restart) VALUES (?, ?, ?, 0, 0)",
                [
                    ("trading_mode", trading_mode, now),
                    ("is_paused", is_paused, now),
                ],
            )
            conn.commit()
    finally:
        conn.close()


def get_control_settings() -> dict:
    """Return all control_settings as a dict."""
    conn = get_connection()
    try:
        rows = conn.execute("SELECT key, value FROM control_settings").fetchall()
        result = {r["key"]: r["value"] for r in rows}
        # Cast booleans for convenience
        if "is_paused" in result:
            result["is_paused"] = result["is_paused"] in ("1", "true", "True", "TRUE", True)
        return result
    finally:
        conn.close()


def get_control_setting(key: str) -> dict | None:
    """Return a single control_setting row as a dict, or None if not found."""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT key, value, updated_at, updated_by, is_secret, requires_restart FROM control_settings WHERE key = ?",
            (key,),
        ).fetchone()
        if row is None:
            return None
        return {
            "key": row["key"],
            "value": row["value"],
            "updated_at": row["updated_at"],
            "updated_by": row["updated_by"],
            "is_secret": bool(row["is_secret"]),
            "requires_restart": bool(row["requires_restart"]),
        }
    finally:
        conn.close()


def update_control_setting(key: str, value: str) -> None:
    """Upsert a control setting value."""
    conn = get_connection()
    try:
        now = datetime.utcnow().isoformat()
        conn.execute(
            "INSERT INTO control_settings (key, value, updated_at) VALUES (?, ?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at",
            (key, str(value), now),
        )
        conn.commit()
    finally:
        conn.close()


def update_control_setting_full(
    key: str,
    value: str,
    updated_by: str | None = None,
    is_secret: bool = False,
    requires_restart: bool = False,
) -> None:
    """Upsert a control setting value with full metadata."""
    conn = get_connection()
    try:
        now = datetime.utcnow().isoformat()
        conn.execute(
            """
            INSERT INTO control_settings (key, value, updated_at, updated_by, is_secret, requires_restart)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET
                value=excluded.value,
                updated_at=excluded.updated_at,
                updated_by=excluded.updated_by,
                is_secret=excluded.is_secret,
                requires_restart=excluded.requires_restart
            """,
            (key, str(value), now, updated_by, 1 if is_secret else 0, 1 if requires_restart else 0),
        )
        conn.commit()
    finally:
        conn.close()
