from app.infrastructure.db.compat import _rewrite_sql_for_postgres


def test_rewrite_insert_or_ignore_to_on_conflict_do_nothing():
    sql, params = _rewrite_sql_for_postgres(
        "INSERT OR IGNORE INTO symbol_parameters (symbol, updated_at) VALUES (?,?)",
        ("AAPL", "2026-05-15T13:30:00"),
    )

    assert "INSERT INTO symbol_parameters" in sql
    assert "ON CONFLICT DO NOTHING" in sql
    assert "%s,%s" in sql or "%s, %s" in sql
    assert params == ("AAPL", "2026-05-15T13:30:00")


def test_rewrite_insert_or_replace_to_postgres_upsert():
    sql, params = _rewrite_sql_for_postgres(
        "INSERT OR REPLACE INTO active_symbols (symbol, market_key, score, selected_at, session_date) VALUES (?, ?, ?, ?, ?)",
        ("AAPL", "STK_US", 0.9, "2026-05-15T13:30:00", "2026-05-15"),
    )

    assert "INSERT INTO active_symbols" in sql
    assert "ON CONFLICT (symbol, market_key, session_date) DO UPDATE SET" in sql
    assert "score=EXCLUDED.score" in sql
    assert "selected_at=EXCLUDED.selected_at" in sql
    assert params[0] == "AAPL"


def test_rewrite_rowid_ordering_to_primary_key_ordering():
    sql, params = _rewrite_sql_for_postgres(
        "SELECT * FROM scanner_results WHERE scan_type=? ORDER BY rowid",
        ("top_gainers",),
    )

    assert "ORDER BY id" in sql
    assert "%s" in sql
    assert params == ("top_gainers",)
