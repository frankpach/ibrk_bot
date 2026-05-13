# tests/ibkr/test_market_permissions.py
import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from app.ibkr.market_permissions import (
    _probe_contract,
    discover_permissions_async,
    run_permission_discovery,
    get_permissions_report,
)


@pytest.mark.asyncio
async def test_probe_contract_success():
    mock_ib = MagicMock()
    mock_detail = MagicMock()
    mock_detail.validExchanges = "SMART,AMEX"
    mock_ib.reqContractDetailsAsync = AsyncMock(return_value=[mock_detail])
    result = await _probe_contract(mock_ib, "STK", "AAPL", "SMART", "USD")
    assert result is not None
    assert result["sec_type"] == "STK"
    assert "SMART" in result["valid_exchanges"]


@pytest.mark.asyncio
async def test_probe_contract_no_details():
    mock_ib = MagicMock()
    mock_ib.reqContractDetailsAsync = AsyncMock(return_value=[])
    result = await _probe_contract(mock_ib, "STK", "AAPL", "SMART", "USD")
    assert result is None


@pytest.mark.asyncio
async def test_probe_contract_exception():
    mock_ib = MagicMock()
    mock_ib.reqContractDetailsAsync = AsyncMock(side_effect=Exception("fail"))
    result = await _probe_contract(mock_ib, "STK", "AAPL", "SMART", "USD")
    assert result is None


@pytest.mark.asyncio
async def test_discover_permissions_async():
    mock_ib = MagicMock()
    mock_detail = MagicMock()
    mock_detail.validExchanges = "SMART"
    mock_ib.reqContractDetailsAsync = AsyncMock(return_value=[mock_detail])
    results = await discover_permissions_async(mock_ib)
    assert len(results) > 0
    assert results[0]["available"] is True


@patch("asyncio.run")
@patch("app.db.database.upsert_market_permissions")
def test_run_permission_discovery(mock_upsert, mock_asyncio_run):
    mock_asyncio_run.return_value = [
        {"key": "STK_US", "label": "Stock US", "sec_type": "STK", "available": True, "valid_exchanges": "SMART", "checked_at": "2024-01-01T00:00:00"}
    ]
    result = run_permission_discovery(None)
    assert len(result) == 1
    mock_upsert.assert_called_once()


@patch("asyncio.run", side_effect=Exception("fail"))
def test_run_permission_discovery_exception(mock_asyncio_run):
    result = run_permission_discovery(None)
    assert result == []


@patch("app.db.database.get_market_permissions_age_hours", return_value=12)
@patch("app.db.database.get_market_permissions")
def test_get_permissions_report_cached(mock_get, mock_age):
    mock_get.return_value = [
        {"key": "STK_US", "label": "Stock US", "sec_type": "STK", "available": True, "valid_exchanges": "SMART", "checked_at": "2024-01-01T00:00:00"}
    ]
    report = get_permissions_report()
    assert report["cache_age_hours"] == 12
    assert len(report["available"]) == 1


@patch("app.db.database.get_market_permissions_age_hours", return_value=25)
@patch("app.ibkr.market_permissions.run_permission_discovery")
def test_get_permissions_report_refresh(mock_run, mock_age):
    mock_run.return_value = [
        {"key": "STK_US", "label": "Stock US", "sec_type": "STK", "available": True, "valid_exchanges": "SMART", "checked_at": "2024-01-01T00:00:00"}
    ]
    report = get_permissions_report(force_refresh=True)
    mock_run.assert_called_once()
    assert len(report["available"]) == 1


@patch("app.db.database.get_market_permissions_age_hours", return_value=None)
@patch("app.ibkr.market_permissions.run_permission_discovery")
def test_get_permissions_report_no_cache(mock_run, mock_age):
    mock_run.return_value = []
    report = get_permissions_report()
    assert report["total"] == 0
    assert report["checked_at"] is None
