# tests/system/test_reconciler.py
from unittest.mock import MagicMock, patch
from datetime import datetime
from app.system.reconciler import reconcile_positions
from app.db.models import Trade


def test_reconcile_closes_orphan_db_trades():
    trade = Trade(
        id=1, symbol="AAPL", action="BUY", quantity=10,
        entry_price=100.0, stop_loss_price=98.0,
        take_profit_price=110.0, stop_loss_pct=0.02,
        take_profit_pct=0.06, signal_strength="STRONG",
        llm_justification="test", status="OPEN",
        exit_price=None, exit_reason=None, pnl_usd=None, pnl_pct=None,
        opened_at=datetime.utcnow(), closed_at=None, order_id="1",
    )
    with patch("app.system.reconciler.get_open_trades", return_value=[trade]), \
         patch("app.system.reconciler.close_trade") as mock_close, \
         patch("app.system.reconciler.insert_trade") as mock_insert, \
         patch("app.system.reconciler.notify"):
        ib_client = MagicMock()
        ib_client.get_portfolio.return_value = []
        result = reconcile_positions(ib_client)
        assert result["closed"] == 1
        mock_close.assert_called_once()
        mock_insert.assert_not_called()


def test_reconcile_creates_missing_ib_positions():
    with patch("app.system.reconciler.get_open_trades", return_value=[]), \
         patch("app.system.reconciler.close_trade") as mock_close, \
         patch("app.system.reconciler.insert_trade") as mock_insert, \
         patch("app.system.reconciler.notify"):
        ib_client = MagicMock()
        ib_client.get_portfolio.return_value = [
            {"symbol": "TSLA", "quantity": 5.0, "avg_cost": 200.0}
        ]
        result = reconcile_positions(ib_client)
        assert result["created"] == 1
        mock_insert.assert_called_once()
        mock_close.assert_not_called()


def test_reconcile_ib_error():
    with patch("app.system.reconciler.get_open_trades", return_value=[]):
        ib_client = MagicMock()
        ib_client.get_portfolio.side_effect = Exception("IB down")
        result = reconcile_positions(ib_client)
        assert result == {"closed": 0, "created": 0}


def test_reconcile_no_changes():
    trade = Trade(
        id=1, symbol="AAPL", action="BUY", quantity=10,
        entry_price=100.0, stop_loss_price=98.0,
        take_profit_price=110.0, stop_loss_pct=0.02,
        take_profit_pct=0.06, signal_strength="STRONG",
        llm_justification="test", status="OPEN",
        exit_price=None, exit_reason=None, pnl_usd=None, pnl_pct=None,
        opened_at=datetime.utcnow(), closed_at=None, order_id="1",
    )
    with patch("app.system.reconciler.get_open_trades", return_value=[trade]), \
         patch("app.system.reconciler.close_trade") as mock_close, \
         patch("app.system.reconciler.insert_trade") as mock_insert, \
         patch("app.system.reconciler.notify") as mock_notify:
        ib_client = MagicMock()
        ib_client.get_portfolio.return_value = [
            {"symbol": "AAPL", "quantity": 10.0, "avg_cost": 100.0}
        ]
        result = reconcile_positions(ib_client)
        assert result == {"closed": 0, "created": 0}
        mock_close.assert_not_called()
        mock_insert.assert_not_called()
        mock_notify.assert_not_called()
