# tests/test_control_seed.py
"""Tests for get_control_setting_value and seed_control_setting."""
from app.infrastructure.db.compat import get_control_setting_value, seed_control_setting


def test_get_returns_default_when_missing():
    result = get_control_setting_value("nonexistent_key_xyz", "my_default")
    assert result == "my_default"


def test_seed_inserts_and_get_returns_value():
    seed_control_setting("test_seed_key_abc", "test_value_123")
    result = get_control_setting_value("test_seed_key_abc", "fallback")
    assert result == "test_value_123"


def test_seed_is_idempotent():
    seed_control_setting("test_idempotent_key", "first_value")
    seed_control_setting("test_idempotent_key", "second_value")  # should not overwrite
    result = get_control_setting_value("test_idempotent_key", "")
    assert result == "first_value"


def test_get_returns_empty_string_default_when_no_default_given():
    result = get_control_setting_value("another_missing_key_xyz")
    assert result == ""
