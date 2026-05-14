"""Patch IBKRClient so tests/api/ can import app.api.main without a live IB connection."""
import sys
import pytest
from unittest.mock import MagicMock, patch

TEST_CONTROL_KEY = "test-control-key"


@pytest.fixture(autouse=True)
def _patch_ibkr_client():
    """Prevent IBKRClient.__init__ from trying to connect to IB Gateway."""
    import app.config.settings as settings_mod
    old_key = settings_mod.API_CONTROL_KEY
    settings_mod.API_CONTROL_KEY = TEST_CONTROL_KEY
    mock_client = MagicMock()
    mock_client.ib.isConnected.return_value = False
    with patch("app.ibkr.client.IBKRClient", return_value=mock_client):
        # Remove any cached import of app.api.main so the patch takes effect
        for mod in list(sys.modules.keys()):
            if "app.api.main" in mod:
                del sys.modules[mod]
        yield mock_client
    settings_mod.API_CONTROL_KEY = old_key
