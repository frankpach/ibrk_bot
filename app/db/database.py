# app/db/database.py
"""Capa de acceso a SQLite con WAL, índices y funciones unificadas."""
import sqlite3
from datetime import datetime, timedelta

from app.config.settings import DB_PATH, ALLOWED_SYMBOLS
from app.db.models import Signal, Trade, Pattern, Decision


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    conn = get_connection()
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
        CREATE INDEX IF NOT EXISTS idx_signals_processed ON signals(processed);
        CREATE INDEX IF NOT EXISTS idx_signals_created ON signals(created_at);

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
        CREATE INDEX IF NOT EXISTS idx_trades_status ON trades(status);
        CREATE INDEX IF NOT EXISTS idx_trades_symbol ON trades(symbol);
        CREATE INDEX IF NOT EXISTS idx_trades_opened ON trades(opened_at);

        CREATE TABLE IF NOT EXISTS patterns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL, pattern_text TEXT NOT NULL,
            win_count INTEGER DEFAULT 0, loss_count INTEGER DEFAULT 0,
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_patterns_symbol ON patterns(symbol);

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
    now = datetime.utcnow().isoformat()
    for sym in ALLOWED_SYMBOLS:
        conn.execute(
            "INSERT OR IGNORE INTO symbol_config (symbol, approved, proposed_by, created_at) VALUES (?,1,'human',?)",
            (sym, now)
        )
    conn.commit()
    conn.close()


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


def get_pending_signals() -> list[Signal]:
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


def get_open_trades() -> list[Trade]:
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


def get_trade_by_id(trade_id: int) -> Trade | None:
    conn = get_connection()
    row = conn.execute("SELECT * FROM trades WHERE id=?", (trade_id,)).fetchone()
    conn.close()
    if not row:
        return None
    return Trade(
        id=row["id"], symbol=row["symbol"], action=row["action"],
        quantity=row["quantity"], entry_price=row["entry_price"],
        stop_loss_price=row["stop_loss_price"], take_profit_price=row["take_profit_price"],
        stop_loss_pct=row["stop_loss_pct"], take_profit_pct=row["take_profit_pct"],
        signal_strength=row["signal_strength"], llm_justification=row["llm_justification"],
        status=row["status"], exit_price=row["exit_price"], exit_reason=row["exit_reason"],
        pnl_usd=row["pnl_usd"], pnl_pct=row["pnl_pct"],
        opened_at=datetime.fromisoformat(row["opened_at"]),
        closed_at=datetime.fromisoformat(row["closed_at"]) if row["closed_at"] else None,
        order_id=row["order_id"],
    )


def close_trade(trade_id: int, exit_price: float, exit_reason: str, pnl_usd: float, pnl_pct: float):
    conn = get_connection()
    conn.execute(
        "UPDATE trades SET status='CLOSED',exit_price=?,exit_reason=?,pnl_usd=?,pnl_pct=?,closed_at=? WHERE id=?",
        (exit_price, exit_reason, pnl_usd, pnl_pct, datetime.utcnow().isoformat(), trade_id)
    )
    conn.commit()
    conn.close()


def get_today_pnl() -> float | None:
    """Retorna la suma de P&L de trades cerrados hoy."""
    conn = get_connection()
    today = datetime.utcnow().strftime("%Y-%m-%d")
    row = conn.execute(
        "SELECT SUM(pnl_usd) as total FROM trades WHERE status='CLOSED' AND closed_at LIKE ?",
        (f"{today}%",)
    ).fetchone()
    conn.close()
    return row["total"] if row and row["total"] is not None else 0.0


def get_patterns_for_symbol(symbol: str) -> list[Pattern]:
    conn = get_connection()
    rows = conn.execute("SELECT * FROM patterns WHERE symbol=? ORDER BY win_count DESC", (symbol,)).fetchall()
    conn.close()
    return [Pattern(
        id=r["id"], symbol=r["symbol"], pattern_text=r["pattern_text"],
        win_count=r["win_count"], loss_count=r["loss_count"],
        created_at=datetime.fromisoformat(r["created_at"]),
        updated_at=datetime.fromisoformat(r["updated_at"]),
    ) for r in rows]


def upsert_pattern(pattern: Pattern) -> int:
    """Inserta o actualiza un patrón existente para evitar duplicados."""
    conn = get_connection()
    existing = conn.execute(
        "SELECT id, win_count, loss_count FROM patterns WHERE symbol=? AND pattern_text=?",
        (pattern.symbol, pattern.pattern_text)
    ).fetchone()
    if existing:
        new_wins = existing["win_count"] + pattern.win_count
        new_losses = existing["loss_count"] + pattern.loss_count
        conn.execute(
            "UPDATE patterns SET win_count=?, loss_count=?, updated_at=? WHERE id=?",
            (new_wins, new_losses, pattern.updated_at.isoformat(), existing["id"])
        )
        conn.commit()
        conn.close()
        return existing["id"]

    cur = conn.execute(
        "INSERT INTO patterns (symbol,pattern_text,win_count,loss_count,created_at,updated_at) VALUES (?,?,?,?,?,?)",
        (pattern.symbol, pattern.pattern_text, pattern.win_count, pattern.loss_count,
         pattern.created_at.isoformat(), pattern.updated_at.isoformat())
    )
    conn.commit()
    row_id = cur.lastrowid
    conn.close()
    return row_id


def get_approved_symbols() -> list[str]:
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
    """Guarda un símbolo propuesto pendiente de aprobación."""
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
    """Aprueba un símbolo propuesto para que el scanner lo incluya."""
    conn = get_connection()
    conn.execute("UPDATE symbol_config SET approved=1 WHERE symbol=?", (symbol.upper(),))
    conn.commit()
    conn.close()


def get_pending_proposals() -> list[dict]:
    """Retorna símbolos propuestos pendientes de aprobación."""
    conn = get_connection()
    rows = conn.execute("SELECT symbol, proposed_by, created_at FROM symbol_config WHERE approved=0").fetchall()
    conn.close()
    return [{"symbol": r["symbol"], "proposed_by": r["proposed_by"], "created_at": r["created_at"]} for r in rows]
