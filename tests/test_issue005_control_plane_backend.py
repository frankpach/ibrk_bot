# tests/test_issue005_control_plane_backend.py
"""Tests for Issue 005: Control Plane Backend."""
from __future__ import annotations

import os
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest
from cryptography.fernet import Fernet
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.application.event_bus import EventBus
from app.application.services.setting_validator import SettingValidator, SettingValidationError
from app.application.use_cases.update_control_setting import (
    UpdateControlSettingUseCase,
    UpdateSettingCommand,
)
from app.application.use_cases.control_queries import (
    GetAllSettingsQuery,
    GetSettingQuery,
    GetAuditLogQuery,
    GetSystemStatusQuery,
)
from app.domain.trading.events import ControlSettingChanged
from app.infrastructure.system.secret_manager import SecretManager
from app.infrastructure.db.compat import get_connection, get_control_setting, update_control_setting_full


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def secret_manager():
    old_key = os.environ.get("SECRET_ENCRYPTION_KEY")
    test_key = Fernet.generate_key().decode()
    os.environ["SECRET_ENCRYPTION_KEY"] = test_key
    sm = SecretManager()
    yield sm
    if old_key is not None:
        os.environ["SECRET_ENCRYPTION_KEY"] = old_key
    else:
        os.environ.pop("SECRET_ENCRYPTION_KEY", None)


@pytest.fixture
def event_bus():
    return EventBus()


# ---------------------------------------------------------------------------
# SecretManager tests
# ---------------------------------------------------------------------------

def test_secret_manager_encrypts_and_decrypts(secret_manager):
    ciphertext = secret_manager.encrypt("my-secret")
    assert ciphertext != "my-secret"
    assert secret_manager.decrypt(ciphertext) == "my-secret"


def test_secret_manager_detects_encrypted(secret_manager):
    ciphertext = secret_manager.encrypt("my-secret")
    assert secret_manager.is_encrypted(ciphertext) is True
    assert secret_manager.is_encrypted("plaintext") is False


def test_secret_manager_missing_key_raises():
    old = os.environ.pop("SECRET_ENCRYPTION_KEY", None)
    try:
        with pytest.raises(RuntimeError, match="SECRET_ENCRYPTION_KEY"):
            SecretManager()
    finally:
        if old is not None:
            os.environ["SECRET_ENCRYPTION_KEY"] = old


# ---------------------------------------------------------------------------
# SettingValidator tests
# ---------------------------------------------------------------------------

def test_validator_accepts_valid_float():
    result = SettingValidator.validate("max_risk_pct", "0.015")
    assert result == 0.015


def test_validator_rejects_negative_risk():
    with pytest.raises(SettingValidationError, match=">="):
        SettingValidator.validate("max_risk_pct", "-0.5")


def test_validator_rejects_out_of_range():
    with pytest.raises(SettingValidationError, match="max"):
        SettingValidator.validate("max_risk_pct", "0.50")


def test_validator_accepts_valid_int():
    result = SettingValidator.validate("max_positions", "5")
    assert result == 5


def test_validator_rejects_zero_positions():
    with pytest.raises(SettingValidationError, match=">="):
        SettingValidator.validate("max_positions", "0")


def test_validator_accepts_enum():
    result = SettingValidator.validate("trading_mode", "paper")
    assert result == "paper"


def test_validator_rejects_invalid_enum():
    with pytest.raises(SettingValidationError, match="one of"):
        SettingValidator.validate("trading_mode", "invalid")


def test_validator_unknown_key_passes_through():
    result = SettingValidator.validate("custom_key", "anything")
    assert result == "anything"


# ---------------------------------------------------------------------------
# UpdateControlSettingUseCase tests
# ---------------------------------------------------------------------------

def test_update_setting_persists_and_publishes_event(secret_manager, event_bus):
    use_case = UpdateControlSettingUseCase(event_bus=event_bus, secret_manager=secret_manager)
    events = []
    event_bus.subscribe(ControlSettingChanged, events.append)

    cmd = UpdateSettingCommand(key="max_risk_pct", value="0.015", changed_by="test")
    result = use_case.execute(cmd)

    assert result.success is True
    assert result.requires_restart is False
    row = get_control_setting("max_risk_pct")
    assert row is not None
    assert row["value"] == "0.015"
    assert len(events) == 1
    assert events[0].key == "max_risk_pct"


def test_update_secret_encrypts_value(secret_manager, event_bus):
    use_case = UpdateControlSettingUseCase(event_bus=event_bus, secret_manager=secret_manager)
    cmd = UpdateSettingCommand(key="llm_api_key", value="sk-live-123", changed_by="admin")
    result = use_case.execute(cmd)

    assert result.success is True
    row = get_control_setting("llm_api_key")
    assert row is not None
    assert row["is_secret"] is True
    # Value in DB must be encrypted (not plaintext)
    assert row["value"] != "sk-live-123"
    assert secret_manager.is_encrypted(row["value"]) is True


def test_update_invalid_value_returns_error(secret_manager, event_bus):
    use_case = UpdateControlSettingUseCase(event_bus=event_bus, secret_manager=secret_manager)
    cmd = UpdateSettingCommand(key="max_risk_pct", value="-0.5", changed_by="test")
    result = use_case.execute(cmd)

    assert result.success is False
    assert result.error is not None
    assert ">=" in result.error


def test_update_without_secret_manager_returns_error(event_bus):
    use_case = UpdateControlSettingUseCase(event_bus=event_bus, secret_manager=None)
    cmd = UpdateSettingCommand(key="llm_api_key", value="sk-live", changed_by="test")
    result = use_case.execute(cmd)

    assert result.success is False
    assert "SecretManager not configured" in result.error


# ---------------------------------------------------------------------------
# Query tests
# ---------------------------------------------------------------------------

def test_get_all_settings_masks_secrets(secret_manager):
    # Seed a secret and a public setting
    update_control_setting_full("telegram_bot_token", "secret-val", is_secret=True)
    update_control_setting_full("max_risk_pct", "0.02", is_secret=False)

    query = GetAllSettingsQuery(secret_manager=secret_manager)
    settings = {s["key"]: s for s in query.execute()}

    assert settings["telegram_bot_token"]["value"] == "••••••••"
    assert settings["telegram_bot_token"]["is_secret"] is True
    assert settings["max_risk_pct"]["value"] == "0.02"
    assert settings["max_risk_pct"]["is_secret"] is False


def test_get_setting_query_reveals_secret(secret_manager):
    update_control_setting_full("llm_api_key", secret_manager.encrypt("real-key"), is_secret=True)

    query = GetSettingQuery(secret_manager=secret_manager)
    result = query.execute("llm_api_key")

    assert result is not None
    assert result["value"] == "••••••••"
    assert result["is_secret"] is True
    assert result["decryption_failed"] is False


def test_get_setting_query_detects_decryption_failure(secret_manager):
    # Store a valid Fernet token from a DIFFERENT key so decryption fails
    other_key = Fernet.generate_key()
    other_fernet = Fernet(other_key)
    bad_ciphertext = other_fernet.encrypt(b"real-key").decode()
    update_control_setting_full("llm_api_key", bad_ciphertext, is_secret=True)

    query = GetSettingQuery(secret_manager=secret_manager)
    result = query.execute("llm_api_key")

    assert result is not None
    assert result["decryption_failed"] is True
    assert result["value"] == "••••••••"


def test_get_audit_log_query_is_paginated():
    # Seed audit log entries
    conn = get_connection()
    now = datetime.now(timezone.utc).isoformat()
    for i in range(5):
        conn.execute(
            """INSERT INTO audit_log (event_type, entity_type, occurred_at)
               VALUES (?, ?, ?)""",
            ("test_event", f"entity_{i}", now),
        )
    conn.commit()
    conn.close()

    query = GetAuditLogQuery()
    result = query.execute(limit=2, offset=0)
    assert len(result["entries"]) == 2
    assert result["total"] == 5


# ---------------------------------------------------------------------------
# API integration tests
# ---------------------------------------------------------------------------

@pytest.fixture
def client(secret_manager):
    # Set control keys without reloading settings (would clobber DATABASE_URL from _init_test_db)
    import app.config.settings as settings_mod
    import app.infrastructure.db.compat as db_mod
    old_control = getattr(settings_mod, "API_CONTROL_KEY", None)
    old_admin = getattr(settings_mod, "API_ADMIN_KEY", None)
    settings_mod.API_CONTROL_KEY = "test-control-key"
    settings_mod.API_ADMIN_KEY = "test-admin-key"
    from app.api.main import app
    with TestClient(app) as c:
        yield c
    if old_control is not None:
        settings_mod.API_CONTROL_KEY = old_control
    if old_admin is not None:
        settings_mod.API_ADMIN_KEY = old_admin


def test_get_control_status_is_public(client):
    resp = client.get("/control/status")
    assert resp.status_code == 200
    assert "mode" in resp.json()


def test_get_settings_masks_secrets(client, secret_manager):
    update_control_setting_full("telegram_bot_token", secret_manager.encrypt("tok"), is_secret=True)
    resp = client.get("/control/settings")
    assert resp.status_code == 200
    settings = {s["key"]: s for s in resp.json()["settings"]}
    assert settings["telegram_bot_token"]["value"] == "••••••••"


def test_put_setting_without_control_key_returns_401(client):
    resp = client.put("/control/settings/max_risk_pct", json={"value": "0.015"})
    assert resp.status_code == 401


def test_put_setting_with_control_key_succeeds(client):
    resp = client.put(
        "/control/settings/max_risk_pct",
        json={"value": "0.015"},
        headers={"X-Control-Key": "test-control-key"},
    )
    assert resp.status_code == 200
    assert resp.json()["success"] is True


def test_put_invalid_setting_returns_422(client):
    resp = client.put(
        "/control/settings/max_risk_pct",
        json={"value": "-0.5"},
        headers={"X-Control-Key": "test-control-key"},
    )
    assert resp.status_code == 422
    assert "error" in resp.json()["detail"]


def test_put_secret_without_admin_key_returns_403(client):
    resp = client.put(
        "/control/settings/llm_api_key",
        json={"value": "sk-new"},
        headers={"X-Control-Key": "test-control-key"},
    )
    assert resp.status_code == 403


def test_put_secret_with_admin_key_succeeds(client):
    resp = client.put(
        "/control/settings/llm_api_key",
        json={"value": "sk-new"},
        headers={
            "X-Control-Key": "test-control-key",
            "X-Admin-Key": "test-admin-key",
        },
    )
    assert resp.status_code == 200
    assert resp.json()["success"] is True

    # Verify DB contains encrypted value
    row = get_control_setting("llm_api_key")
    assert row["value"] != "sk-new"


def test_get_single_setting_reveals_no_secret(client, secret_manager):
    update_control_setting_full("llm_api_key", secret_manager.encrypt("real-key"), is_secret=True)
    resp = client.get("/control/settings/llm_api_key")
    assert resp.status_code == 200
    assert resp.json()["value"] == "••••••••"
    assert resp.json()["is_secret"] is True


def test_audit_log_endpoint_requires_control_key(client):
    resp = client.get("/control/audit")
    assert resp.status_code == 401


def test_audit_log_returns_entries(client, secret_manager):
    # Trigger a setting change to create an audit entry
    use_case = UpdateControlSettingUseCase(
        event_bus=EventBus(), secret_manager=secret_manager,
    )
    use_case.execute(UpdateSettingCommand(key="max_risk_pct", value="0.02", changed_by="test"))

    resp = client.get(
        "/control/audit",
        headers={"X-Control-Key": "test-control-key"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1
    assert len(data["entries"]) >= 1


def test_jobs_endpoint_is_public(client):
    resp = client.get("/control/jobs")
    assert resp.status_code == 200
    assert "jobs" in resp.json()
