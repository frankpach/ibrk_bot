# tests/llm/test_postmortem.py
from unittest.mock import MagicMock, patch
from datetime import datetime
from app.db.models import Trade
from app.llm.postmortem import _call_opencode, run_postmortem


# ---------- _call_opencode ----------
@patch("subprocess.run")
def test_call_opencode_success(mock_run):
    mock_run.return_value = MagicMock(
        stdout='{"type":"text","part":{"text":"hello"}}\n',
        stderr="",
    )
    result = _call_opencode("prompt")
    assert result == "hello"


@patch("subprocess.run")
def test_call_opencode_timeout(mock_run):
    from subprocess import TimeoutExpired
    mock_run.side_effect = TimeoutExpired("cmd", 60)
    result = _call_opencode("prompt")
    assert result == ""


@patch("subprocess.run")
def test_call_opencode_exception(mock_run):
    mock_run.side_effect = Exception("fail")
    result = _call_opencode("prompt")
    assert result == ""


# ---------- run_postmortem ----------
@patch("app.llm.postmortem.OPENCODE_BIN", None)
def _make_trade(**kwargs):
    defaults = {
        "id": 1, "symbol": "AAPL", "action": "BUY", "quantity": 10,
        "entry_price": 100.0, "stop_loss_price": 95.0, "take_profit_price": 110.0,
        "stop_loss_pct": 0.05, "take_profit_pct": 0.10,
        "signal_strength": "STRONG", "llm_justification": "test",
        "status": "CLOSED", "exit_price": None,
        "opened_at": datetime.now(), "closed_at": None, "order_id": None,
    }
    defaults.update(kwargs)
    return Trade(**defaults)


@patch("app.llm.postmortem.OPENCODE_BIN", None)
def test_run_postmortem_no_bin():
    trade = _make_trade(pnl_pct=0.02, pnl_usd=20.0, exit_reason="TP")
    # should return early without error
    run_postmortem(trade)


@patch("app.llm.postmortem._call_opencode")
@patch("app.llm.postmortem.insert_pattern")
@patch("app.llm.postmortem.notify")
@patch("app.analysis.scorer.update_weights_attenuated")
@patch("app.llm.postmortem.OPENCODE_BIN", "/fake/opencode")
def test_run_postmortem_win(mock_update, mock_notify, mock_insert, mock_call):
    mock_call.return_value = '{"pattern_text":"win pattern","suggestions":[{"dimension":"stop_loss_pct","suggested_multiplier":1.1,"confidence":0.7,"reason":"test"}]}'
    mock_update.return_value = True
    trade = _make_trade(pnl_pct=0.02, pnl_usd=20.0, exit_reason="TP")
    run_postmortem(trade)
    mock_insert.assert_called_once()
    mock_update.assert_called_once()
    mock_notify.assert_called_once()


@patch("app.llm.postmortem._call_opencode")
@patch("app.llm.postmortem.insert_pattern")
@patch("app.llm.postmortem.notify")
@patch("app.llm.postmortem.OPENCODE_BIN", "/fake/opencode")
def test_run_postmortem_loss(mock_notify, mock_insert, mock_call):
    mock_call.return_value = '{"pattern_text":"loss pattern","suggestions":[]}'
    trade = _make_trade(pnl_pct=-0.03, pnl_usd=-30.0, exit_reason="SL")
    run_postmortem(trade)
    mock_insert.assert_called_once()
    mock_notify.assert_called_once()


@patch("app.llm.postmortem._call_opencode")
@patch("app.llm.postmortem.insert_pattern")
@patch("app.llm.postmortem.notify")
@patch("app.analysis.scorer.update_weights_attenuated")
@patch("app.llm.postmortem.OPENCODE_BIN", "/fake/opencode")
def test_run_postmortem_markdown_response(mock_update, mock_notify, mock_insert, mock_call):
    mock_call.return_value = '```json\n{"pattern_text":"md pattern","suggestions":[]}\n```'
    trade = _make_trade(pnl_pct=0.01, pnl_usd=10.0, exit_reason="MANUAL")
    run_postmortem(trade)
    mock_insert.assert_called_once()


@patch("app.llm.postmortem._call_opencode")
@patch("app.llm.postmortem.insert_pattern")
@patch("app.llm.postmortem.notify")
@patch("app.llm.postmortem.OPENCODE_BIN", "/fake/opencode")
def test_run_postmortem_bad_json(mock_notify, mock_insert, mock_call):
    mock_call.return_value = "not json"
    trade = _make_trade(pnl_pct=0.01, pnl_usd=10.0, exit_reason="MANUAL")
    run_postmortem(trade)
    mock_insert.assert_called_once()


@patch("app.llm.postmortem._call_opencode")
@patch("app.llm.postmortem.insert_pattern")
@patch("app.llm.postmortem.notify")
@patch("app.analysis.scorer.update_weights_attenuated")
@patch("app.llm.postmortem.OPENCODE_BIN", "/fake/opencode")
def test_run_postmortem_feature_snapshot(mock_update, mock_notify, mock_insert, mock_call):
    mock_call.return_value = '{"pattern_text":"fs pattern","suggestions":[]}'
    fs = MagicMock()
    fs.to_dict.return_value = {"rsi_14": 50}
    trade = _make_trade(pnl_pct=0.01, pnl_usd=10.0, exit_reason="MANUAL")
    run_postmortem(trade, feature_snapshot=fs)
    mock_insert.assert_called_once()


@patch("app.llm.postmortem._call_opencode")
@patch("app.llm.postmortem.insert_pattern")
@patch("app.llm.postmortem.notify")
@patch("app.analysis.scorer.update_weights_attenuated")
@patch("app.llm.postmortem.OPENCODE_BIN", "/fake/opencode")
def test_run_postmortem_feature_snapshot_exception(mock_update, mock_notify, mock_insert, mock_call):
    mock_call.return_value = '{"pattern_text":"fs err","suggestions":[]}'
    fs = MagicMock()
    fs.to_dict.side_effect = Exception("fail")
    trade = _make_trade(pnl_pct=0.01, pnl_usd=10.0, exit_reason="MANUAL")
    run_postmortem(trade, feature_snapshot=fs)
    mock_insert.assert_called_once()


@patch("app.llm.postmortem._call_opencode")
@patch("app.llm.postmortem.insert_pattern")
@patch("app.llm.postmortem.notify")
@patch("app.analysis.scorer.update_weights_attenuated")
@patch("app.llm.postmortem.OPENCODE_BIN", "/fake/opencode")
def test_run_postmortem_low_confidence_suggestion(mock_update, mock_notify, mock_insert, mock_call):
    mock_call.return_value = '{"pattern_text":"low conf","suggestions":[{"dimension":"stop_loss_pct","suggested_multiplier":1.1,"confidence":0.3,"reason":"test"}]}'
    trade = _make_trade(pnl_pct=0.01, pnl_usd=10.0, exit_reason="MANUAL")
    run_postmortem(trade)
    mock_update.assert_not_called()


@patch("app.llm.postmortem._call_opencode")
@patch("app.llm.postmortem.insert_pattern")
@patch("app.llm.postmortem.notify")
@patch("app.analysis.scorer.update_weights_attenuated")
@patch("app.llm.postmortem.OPENCODE_BIN", "/fake/opencode")
def test_run_postmortem_adjustment_exception(mock_update, mock_notify, mock_insert, mock_call):
    mock_call.return_value = '{"pattern_text":"adj err","suggestions":[{"dimension":"stop_loss_pct","suggested_multiplier":1.1,"confidence":0.7,"reason":"test"}]}'
    mock_update.side_effect = Exception("adj fail")
    trade = _make_trade(pnl_pct=0.01, pnl_usd=10.0, exit_reason="MANUAL")
    run_postmortem(trade)
    mock_insert.assert_called_once()
