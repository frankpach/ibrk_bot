"""Tests for app/scanner/news_fetcher.py"""
from unittest.mock import MagicMock, patch, call


def test_fetch_and_cache_news_empty_symbols():
    """With no approved symbols, returns 0 and does not call insert_news_cache."""
    from app.scanner.news_fetcher import fetch_and_cache_news

    data_layer = MagicMock()

    with patch("app.db.database.get_approved_symbols_with_meta", return_value=[]), \
         patch("app.db.database.clear_news_cache_older_than"), \
         patch("app.db.database.insert_news_cache") as mock_insert:
        result = fetch_and_cache_news(data_layer)

    assert result == 0
    mock_insert.assert_not_called()


def test_fetch_and_cache_news_inserts_articles():
    """With 2 news items per symbol, insert_news_cache is called twice per symbol."""
    from app.scanner.news_fetcher import fetch_and_cache_news

    data_layer = MagicMock()
    data_layer.get_news.return_value = [
        {"title": "AAPL beats earnings", "provider": "Reuters",
         "sentiment": "positive", "article_id": "101", "date": "2026-05-13"},
        {"title": "AAPL new product launch", "provider": "Bloomberg",
         "sentiment": "neutral", "article_id": "102", "date": "2026-05-13"},
    ]

    symbols = [{"symbol": "AAPL"}]

    with patch("app.db.database.get_approved_symbols_with_meta", return_value=symbols), \
         patch("app.db.database.clear_news_cache_older_than"), \
         patch("app.db.database.insert_news_cache") as mock_insert, \
         patch("time.sleep"):  # skip rate-limit delay in tests
        result = fetch_and_cache_news(data_layer)

    assert result == 2
    assert mock_insert.call_count == 2
    # Verify first call args
    first_call = mock_insert.call_args_list[0]
    assert first_call.kwargs["symbol"] == "AAPL"
    assert first_call.kwargs["headline"] == "AAPL beats earnings"
    assert first_call.kwargs["sentiment"] == "positive"


def test_fetch_and_cache_news_skips_empty_headline():
    """Articles with empty title are not inserted."""
    from app.scanner.news_fetcher import fetch_and_cache_news

    data_layer = MagicMock()
    data_layer.get_news.return_value = [
        {"title": "", "provider": "Reuters", "sentiment": "neutral",
         "article_id": "103", "date": "2026-05-13"},
        {"title": "Valid headline", "provider": "Reuters", "sentiment": "positive",
         "article_id": "104", "date": "2026-05-13"},
    ]

    with patch("app.db.database.get_approved_symbols_with_meta", return_value=[{"symbol": "TSLA"}]), \
         patch("app.db.database.clear_news_cache_older_than"), \
         patch("app.db.database.insert_news_cache") as mock_insert, \
         patch("time.sleep"):
        result = fetch_and_cache_news(data_layer)

    assert result == 1
    assert mock_insert.call_count == 1


def test_fetch_and_cache_news_handles_news_fetch_error():
    """A failing get_news call is caught and processing continues."""
    from app.scanner.news_fetcher import fetch_and_cache_news

    data_layer = MagicMock()
    data_layer.get_news.side_effect = RuntimeError("IB disconnected")

    with patch("app.db.database.get_approved_symbols_with_meta", return_value=[{"symbol": "MSFT"}]), \
         patch("app.db.database.clear_news_cache_older_than"), \
         patch("app.db.database.insert_news_cache") as mock_insert, \
         patch("time.sleep"):
        result = fetch_and_cache_news(data_layer)

    assert result == 0
    mock_insert.assert_not_called()
