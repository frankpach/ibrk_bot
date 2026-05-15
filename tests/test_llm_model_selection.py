# tests/test_llm_model_selection.py
"""Tests for get_llm_model_for_task per-task model selection."""
from unittest.mock import patch
from app.llm.agent import get_llm_model_for_task


def test_fallback_when_db_fails():
    with patch("app.infrastructure.db.compat.get_control_setting_value",
               side_effect=Exception("db down")):
        model = get_llm_model_for_task("analysis")
    assert model  # not empty
    assert isinstance(model, str)


def test_returns_db_value_for_analysis():
    with patch("app.infrastructure.db.compat.get_control_setting_value",
               return_value="opencode-go/claude-sonnet-4"):
        model = get_llm_model_for_task("analysis")
    assert model == "opencode-go/claude-sonnet-4"


def test_per_task_key_mapping():
    calls = []
    def fake_get(key, default):
        calls.append(key)
        return default
    with patch("app.infrastructure.db.compat.get_control_setting_value", side_effect=fake_get):
        get_llm_model_for_task("signal")
        get_llm_model_for_task("postmortem")
    assert "llm_model_signal" in calls
    assert "llm_model_postmortem" in calls


def test_unknown_task_falls_back_to_opencode_model_key():
    calls = []
    def fake_get(key, default):
        calls.append(key)
        return default
    with patch("app.infrastructure.db.compat.get_control_setting_value", side_effect=fake_get):
        get_llm_model_for_task("unknown_task")
    assert "opencode_model" in calls


def test_empty_db_value_returns_default():
    with patch("app.infrastructure.db.compat.get_control_setting_value",
               return_value=""):
        model = get_llm_model_for_task("analysis")
    assert model  # should return default, not empty string
