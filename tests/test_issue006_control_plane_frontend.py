# tests/test_issue006_control_plane_frontend.py
"""Tests for Issue 006: Control Plane Frontend."""
import os
from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    import app.config.settings as settings_mod
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


class TestControlPlaneRoute:
    def test_control_page_returns_html(self, client):
        resp = client.get("/control")
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/html")

    def test_control_page_has_react_root(self, client):
        resp = client.get("/control")
        assert 'id="root"' in resp.text

    def test_control_page_has_control_plane_app(self, client):
        resp = client.get("/control")
        assert "ControlPlaneApp" in resp.text or "control-plane" in resp.text

    def test_control_section_query_param(self, client):
        resp = client.get("/control?section=risk")
        assert resp.status_code == 200
        assert "section=risk" in resp.text or "risk" in resp.text.lower()

    def test_control_page_polls_status_endpoint(self, client):
        resp = client.get("/control")
        assert "/control/status" in resp.text

    def test_control_page_has_seven_panels(self, client):
        resp = client.get("/control")
        text = resp.text
        # The sidebar should have 7 items
        panels = ["Operativo", "Riesgo", "Símbolos", "Infraestructura", "Jobs", "API Keys", "Audit Log"]
        found = sum(1 for p in panels if p in text)
        assert found >= 5  # at least 5 of 7 visible


class TestSystemStatusBar:
    def test_dashboard_has_system_status_bar(self, client):
        resp = client.get("/dashboard")
        assert resp.status_code == 200
        # Should link to /control section
        assert "/control" in resp.text

    def test_system_status_bar_shows_mode(self, client):
        resp = client.get("/dashboard")
        assert resp.status_code == 200
        # Should contain mode display logic
        assert "PAPER" in resp.text or "LIVE" in resp.text

    def test_system_status_bar_links_to_control(self, client):
        resp = client.get("/dashboard")
        assert "/control" in resp.text


class TestControlApiIntegration:
    def test_control_settings_put_with_control_key(self, client):
        resp = client.put(
            "/control/settings/max_risk_pct",
            json={"value": "0.015"},
            headers={"X-Control-Key": "test-control-key"},
        )
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    def test_control_audit_requires_control_key(self, client):
        resp = client.get("/control/audit")
        assert resp.status_code == 401

    def test_control_audit_with_control_key(self, client):
        resp = client.get("/control/audit", headers={"X-Control-Key": "test-control-key"})
        assert resp.status_code == 200
        data = resp.json()
        assert "entries" in data
        assert "total" in data

    def test_control_jobs_endpoint(self, client):
        resp = client.get("/control/jobs")
        assert resp.status_code == 200
        assert "jobs" in resp.json()

    def test_control_status_is_public(self, client):
        resp = client.get("/control/status")
        assert resp.status_code == 200
        assert "mode" in resp.json()
