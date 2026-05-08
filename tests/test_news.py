# tests/test_news.py
from unittest.mock import patch, MagicMock
from app.scanner.news import get_news_summary, _extract_sentiment


def test_extract_sentiment_positive():
    text = "AAPL stock surges to record high after strong earnings beat"
    assert _extract_sentiment(text) == "positive"


def test_extract_sentiment_negative():
    text = "AAPL crashes amid recession fears and disappointing revenue"
    assert _extract_sentiment(text) == "negative"


def test_extract_sentiment_neutral():
    text = "AAPL announces new product line scheduled for next quarter"
    assert _extract_sentiment(text) == "neutral"


def test_get_news_summary_returns_string():
    with patch("app.scanner.news.feedparser") as mock_fp:
        mock_fp.parse.return_value = MagicMock(entries=[
            MagicMock(title="AAPL beats earnings", summary="Apple reported strong Q3 results"),
            MagicMock(title="Market rallies on Fed news", summary="Stocks rise after Fed decision"),
        ])
        result = get_news_summary("AAPL")
        assert isinstance(result, str)
        assert len(result) > 0


def test_get_news_summary_handles_no_news():
    with patch("app.scanner.news.feedparser") as mock_fp:
        mock_fp.parse.return_value = MagicMock(entries=[])
        result = get_news_summary("FAKE")
        assert "No recent news" in result
