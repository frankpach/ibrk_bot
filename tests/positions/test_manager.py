# tests/positions/test_manager.py
from unittest.mock import MagicMock, patch
from datetime import datetime
from app.positions.manager import check_positions
from app.db.models import Trade


def _open_trade(symbol="AAPL", action="BUY", entry=100.0, sl=98.0, tp=110.0, qty=10, partial=False, partial_done=False, remaining=None, signal_strength="STRONG"):
    return Trade(
        id=1, symbol=symbol, action=action, quantity=qty,
        entry_price=entry, stop_loss_price=sl,
        take_profit_price=tp, stop_loss_pct=0.02,
        take_profit_pct=0.06, signal_strength=signal_strength,
        llm_justification="test", status="OPEN",
        exit_price=None, exit_reason=None, pnl_usd=None, pnl_pct=None,
        opened_at=datetime.utcnow(), closed_at=None, order_id="1",
        trade_status="OPEN", entry_fill_price=entry,
        partial_exit_done=partial_done,
        remaining_quantity=remaining if remaining is not None else qty,
    )


@patch("app.positions.manager.httpx.get")
@patch("app.positions.manager.get_open_trades")
@patch("app.positions.manager.notify")
def test_check_positions_no_trades(mock_notify, mock_get_trades, mock_get):
    mock_get_trades.return_value = []
    check_positions()
    mock_notify.assert_not_called()


@patch("app.positions.manager.httpx.get")
@patch("app.positions.manager.get_open_trades")
def test_check_positions_stop_loss(mock_get_trades, mock_get):
    trade = _open_trade()
    mock_get_trades.return_value = [trade]
    mock_get.return_value = MagicMock(json=lambda: {"market_price": 97.0})
    with patch("app.positions.manager._close_position", return_value=True) as mock_close:
        check_positions()
        mock_close.assert_called_once()
        args = mock_close.call_args
        assert args[0][1] == "STOP_LOSS"


@patch("app.positions.manager.httpx.get")
@patch("app.positions.manager.get_open_trades")
def test_check_positions_take_profit(mock_get_trades, mock_get):
    trade = _open_trade(partial_done=True)  # avoid partial exit
    mock_get_trades.return_value = [trade]
    mock_get.return_value = MagicMock(json=lambda: {"market_price": 111.0})
    with patch("app.positions.manager._close_position", return_value=True) as mock_close:
        check_positions()
        mock_close.assert_called_once()
        assert mock_close.call_args[0][1] == "TAKE_PROFIT"


@patch("app.positions.manager.httpx.get")
@patch("app.positions.manager.get_open_trades")
def test_check_positions_partial_exit(mock_get_trades, mock_get):
    trade = _open_trade(entry=100.0, sl=98.0, qty=10)
    mock_get_trades.return_value = [trade]
    # 1.5x SL = 3.0% gain
    mock_get.return_value = MagicMock(json=lambda: {"market_price": 103.5})
    with patch("app.positions.manager._close_position", return_value=True) as mock_close:
        check_positions()
        mock_close.assert_called_once()
        assert "PARTIAL" in mock_close.call_args[0][1]


@patch("app.positions.manager.httpx.get")
@patch("app.positions.manager.get_open_trades")
@patch("app.positions.manager.update_trade_status")
def test_check_positions_trailing_stop_update(mock_update, mock_get_trades, mock_get):
    trade = _open_trade(entry=100.0, sl=98.0, partial_done=True)
    mock_get_trades.return_value = [trade]
    # 3x SL = 6% gain -> trailing
    mock_get.return_value = MagicMock(json=lambda: {"market_price": 107.0})
    with patch("app.positions.manager._close_position", return_value=False):
        check_positions()
    mock_update.assert_called_once()


@patch("app.positions.manager.httpx.get")
@patch("app.positions.manager.get_open_trades")
def test_check_positions_price_fetch_failure(mock_get_trades, mock_get):
    trade = _open_trade()
    mock_get_trades.return_value = [trade]
    mock_get.side_effect = Exception("network down")
    check_positions()  # should not raise


@patch("app.positions.manager.httpx.get")
@patch("app.positions.manager.get_open_trades")
def test_check_positions_sell_stop_loss(mock_get_trades, mock_get):
    trade = _open_trade(action="SELL", entry=100.0, sl=102.0, tp=94.0)
    mock_get_trades.return_value = [trade]
    mock_get.return_value = MagicMock(json=lambda: {"market_price": 103.0})
    with patch("app.positions.manager._close_position", return_value=True) as mock_close:
        check_positions()
        mock_close.assert_called_once()
        assert mock_close.call_args[0][1] == "STOP_LOSS"


@patch("app.positions.manager.httpx.get")
@patch("app.positions.manager.get_open_trades")
def test_check_positions_sell_take_profit(mock_get_trades, mock_get):
    trade = _open_trade(action="SELL", entry=100.0, sl=102.0, tp=94.0, partial_done=True)
    mock_get_trades.return_value = [trade]
    mock_get.return_value = MagicMock(json=lambda: {"market_price": 93.0})
    with patch("app.positions.manager._close_position", return_value=True) as mock_close:
        check_positions()
        mock_close.assert_called_once()
        assert mock_close.call_args[0][1] == "TAKE_PROFIT"


@patch("app.positions.manager.httpx.get")
@patch("app.positions.manager.get_open_trades")
def test_check_positions_min_profit_medium(mock_get_trades, mock_get):
    trade = _open_trade(signal_strength="MEDIUM", entry=100.0, sl=98.0, tp=110.0, partial_done=True)
    mock_get_trades.return_value = [trade]
    from app.config.settings import MIN_PROFIT_PCT_MEDIUM
    mock_get.return_value = MagicMock(json=lambda: {"market_price": 100.0 + 100.0 * MIN_PROFIT_PCT_MEDIUM + 0.01})
    with patch("app.positions.manager._close_position", return_value=True) as mock_close:
        check_positions()
        mock_close.assert_called_once()
        assert mock_close.call_args[0][1] == "MIN_PROFIT_MEDIUM"


@patch("app.positions.manager.httpx.get")
@patch("app.positions.manager.get_open_trades")
@patch("app.positions.manager.update_trade_status")
def test_check_positions_partial_close_all(mock_update, mock_get_trades, mock_get):
    trade = _open_trade(entry=100.0, sl=98.0, qty=10)
    mock_get_trades.return_value = [trade]
    mock_get.return_value = MagicMock(json=lambda: {"market_price": 103.5})
    mock_partial = MagicMock()
    mock_partial.should_exit = True
    mock_partial.exit_reason = "PARTIAL_EXIT"
    mock_partial.exit_quantity = 5
    mock_partial.close_all = True
    with patch("app.positions.manager._close_position", return_value=True) as mock_close, \
         patch("app.positions.manager.partial_mgr.check_exit", return_value=mock_partial):
        check_positions()
        assert mock_close.call_count == 1
        # partial exit with close_all should trigger continue (no trailing stop update)
        mock_update.assert_not_called()


# ---- _close_position tests ----

@patch("app.positions.manager.get_policy")
@patch("app.positions.manager.notify")
@patch("app.positions.manager.update_trade_status")
@patch("app.ibkr.client.get_client")
@patch("app.ibkr.dedup.PreflightChecker")
def test_close_position_preflight_fail(MockPreflight, mock_get_client, mock_update, mock_notify, mock_get_policy):
    from app.positions.manager import _close_position
    trade = _open_trade()
    mock_preflight = MagicMock()
    mock_preflight.check.return_value = MagicMock(ok=False, reason="market closed")
    MockPreflight.return_value = mock_preflight
    result = _close_position(trade, "STOP_LOSS", 97.0, -0.03, -30.0)
    assert result is False


@patch("app.positions.manager.get_policy")
@patch("app.positions.manager.notify")
@patch("app.positions.manager.update_trade_status")
@patch("app.positions.manager.close_trade")
@patch("app.positions.manager.run_postmortem", side_effect=Exception("postmortem fail"))
@patch("app.positions.manager.get_fill_price_fallback", return_value=105.0)
@patch("app.ibkr.client.get_client")
@patch("app.ibkr.dedup.PreflightChecker")
def test_close_position_full_with_postmortem_error(MockPreflight, mock_get_client, mock_fill, mock_postmortem, mock_close_trade, mock_update, mock_notify, mock_get_policy):
    from app.positions.manager import _close_position
    trade = _open_trade()
    mock_preflight = MagicMock()
    mock_preflight.check.return_value = MagicMock(ok=True, reason=None)
    MockPreflight.return_value = mock_preflight
    mock_client = MagicMock()
    mock_client.place_order.return_value = {"order_id": "999"}
    mock_get_client.return_value = mock_client
    mock_policy = MagicMock()
    mock_policy.should_notify.return_value = True
    mock_get_policy.return_value = mock_policy
    result = _close_position(trade, "TAKE_PROFIT", 105.0, 0.05, 50.0)
    assert result is True
    mock_close_trade.assert_called_once()
    mock_postmortem.assert_called_once()


@patch("app.positions.manager.get_policy")
@patch("app.positions.manager.notify")
@patch("app.positions.manager.update_trade_status")
@patch("app.ibkr.client.get_client")
@patch("app.ibkr.dedup.PreflightChecker")
def test_close_position_partial_exit(MockPreflight, mock_get_client, mock_update, mock_notify, mock_get_policy):
    from app.positions.manager import _close_position
    trade = _open_trade(qty=10, remaining=10)
    mock_preflight = MagicMock()
    mock_preflight.check.return_value = MagicMock(ok=True, reason=None)
    MockPreflight.return_value = mock_preflight
    mock_client = MagicMock()
    mock_client.place_order.return_value = {"order_id": "999"}
    mock_get_client.return_value = mock_client
    mock_policy = MagicMock()
    mock_policy.should_notify.return_value = True
    mock_get_policy.return_value = mock_policy
    result = _close_position(trade, "PARTIAL_EXIT", 103.0, 0.03, 30.0, quantity=5)
    assert result is True
    mock_update.assert_called_once()
    assert trade.partial_exit_done is True
    assert trade.remaining_quantity == 5
