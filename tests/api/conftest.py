"""Patch IBKRClient so tests/api/ can import app.api.main without a live IB connection."""
import sys
import pytest
from unittest.mock import MagicMock, patch


@pytest.fixture(autouse=True)
def _patch_ibkr_client():
    """Prevent IBKRClient.__init__ from trying to connect to IB Gateway."""
    mock_client = MagicMock()
    mock_client.ib.isConnected.return_value = False
    with patch("app.ibkr.client.IBKRClient", return_value=mock_client):
        # Remove any cached import of app.api.main so the patch takes effect
        for mod in list(sys.modules.keys()):
            if "app.api.main" in mod:
                del sys.modules[mod]
        yield mock_client
