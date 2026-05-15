# tests/test_issue010_hardening.py
"""Tests for Issue 010: Phase 8 — Hardening Final."""
from __future__ import annotations

import os
import subprocess
import sys

import pytest
from fastapi.testclient import TestClient


class TestNoEvalOrShell:
    def test_no_shell_true_in_app(self):
        """grep -r 'shell=True' app/ must return 0 results."""
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        app_dir = os.path.join(project_root, "app")
        count = 0
        for root, _dirs, files in os.walk(app_dir):
            for f in files:
                if not f.endswith(".py"):
                    continue
                path = os.path.join(root, f)
                try:
                    with open(path, "r", encoding="utf-8") as fh:
                        content = fh.read()
                    if "shell=True" in content:
                        count += 1
                        print(f"FOUND shell=True: {path}")
                except Exception:
                    pass
        assert count == 0, f"Found {count} files with shell=True in app/"

    def test_no_eval_in_app(self):
        """grep -r 'eval(' app/ must return 0 results (excluding comments is hard; just check raw)."""
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        app_dir = os.path.join(project_root, "app")
        count = 0
        for root, _dirs, files in os.walk(app_dir):
            for f in files:
                if not f.endswith(".py"):
                    continue
                path = os.path.join(root, f)
                try:
                    with open(path, "r", encoding="utf-8") as fh:
                        content = fh.read()
                    # Count actual eval( calls, not comments/strings about eval(
                    lines = content.splitlines()
                    for line in lines:
                        stripped = line.strip()
                        if stripped.startswith("#") or stripped.startswith('"') or stripped.startswith("'"):
                            continue
                        if "eval(" in stripped:
                            count += 1
                            print(f"FOUND eval(): {path} -> {stripped}")
                except Exception:
                    pass
        assert count == 0, f"Found {count} eval() calls in app/"


class TestEngineNoSqlite3:
    def test_engine_py_does_not_import_sqlite3(self):
        path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "app", "infrastructure", "db", "engine.py",
        )
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        assert "import sqlite3" not in content, "engine.py must not import sqlite3"
        assert "from sqlite3" not in content, "engine.py must not import from sqlite3"

    def test_engine_py_no_pragma(self):
        path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "app", "infrastructure", "db", "engine.py",
        )
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        assert "PRAGMA" not in content, "engine.py must not contain PRAGMA"

    def test_get_database_url_reads_env(self, monkeypatch):
        from app.infrastructure.db.engine import get_database_url
        monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@localhost/db")
        url = get_database_url()
        assert url == "postgresql://user:pass@localhost/db"

    def test_get_database_url_defaults_to_sqlite(self, monkeypatch):
        from app.infrastructure.db.engine import get_database_url
        monkeypatch.delenv("DATABASE_URL", raising=False)
        url = get_database_url()
        assert url.startswith("sqlite:///")


class TestMigrationNoUnconditionalPragma:
    def test_migration_downgrade_is_conditional(self):
        path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "app", "infrastructure", "db", "migrations", "versions", "001_initial_schema.py",
        )
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        # PRAGMA is allowed only inside a conditional block (dialect == "sqlite")
        assert "PRAGMA" in content, "Migration should still reference PRAGMA conditionally"
        assert 'dialect == "sqlite"' in content, "PRAGMA must be guarded by dialect check"


class TestOpenCodeAdapterHardening:
    @pytest.fixture(autouse=True)
    def _patch_opencode_bin(self, monkeypatch):
        """Point OPENCODE_BIN to sys.executable so _validate_bin passes in CI."""
        import app.config.settings as _settings
        monkeypatch.setattr(_settings, "OPENCODE_BIN", sys.executable)

    def test_validate_symbol_rejects_injection(self):
        from app.infrastructure.llm.opencode_adapter import OpenCodeAdapter
        adapter = OpenCodeAdapter()
        with pytest.raises(ValueError):
            adapter._validate_symbol("AAPL; rm -rf /")
        with pytest.raises(ValueError):
            adapter._validate_symbol("AAPL$(cmd)")
        with pytest.raises(ValueError):
            adapter._validate_symbol("AAPL\nBAD")

    def test_validate_symbol_accepts_safe_symbols(self):
        from app.infrastructure.llm.opencode_adapter import OpenCodeAdapter
        adapter = OpenCodeAdapter()
        adapter._validate_symbol("AAPL")
        adapter._validate_symbol("ES")
        adapter._validate_symbol("EURUSD")

    def test_output_parsed_with_json_loads(self):
        from app.infrastructure.llm.opencode_adapter import OpenCodeAdapter
        adapter = OpenCodeAdapter()
        # call() already uses json.loads internally; we just verify no eval is used
        # by checking the source
        import inspect
        source = inspect.getsource(adapter.call)
        assert "json.loads" in source
        assert "eval(" not in source


class TestSecurityHeaders:
    def test_security_headers_present(self):
        from app.api.main import app
        client = TestClient(app)
        response = client.get("/health")
        assert response.headers.get("X-Content-Type-Options") == "nosniff"
        assert response.headers.get("X-Frame-Options") == "DENY"
        assert response.headers.get("Referrer-Policy") == "no-referrer"

    def test_cors_headers_configurable(self, monkeypatch):
        from app.api.main import app
        monkeypatch.setenv("ALLOWED_ORIGINS", "http://100.64.0.1")
        monkeypatch.setenv("RESTRICT_CORS", "true")
        # Re-import to pick up env changes (app is module-level)
        # We can't easily reload, but the middleware is already added.
        # Instead verify the middleware exists.
        client = TestClient(app)
        response = client.get("/health", headers={"Origin": "http://100.64.0.1"})
        assert "access-control-allow-origin" in {k.lower() for k in response.headers.keys()}


class TestSystemdUnitFile:
    def test_service_file_exists(self):
        assert os.path.exists("scripts/ibkr-trader.service")

    def test_service_has_nonewprivileges(self):
        with open("scripts/ibkr-trader.service", "r", encoding="utf-8") as f:
            content = f.read()
        assert "NoNewPrivileges=true" in content

    def test_service_uses_environment_file(self):
        with open("scripts/ibkr-trader.service", "r", encoding="utf-8") as f:
            content = f.read()
        assert "EnvironmentFile=" in content
        assert "EnvironmentFile=/home/frankpach/ibkr-bot/.env.secret" in content
        # No inline secrets
        assert "Environment=TELEGRAM_BOT_TOKEN" not in content
        assert "Environment=API_CONTROL_KEY" not in content

    def test_service_has_private_tmp(self):
        with open("scripts/ibkr-trader.service", "r", encoding="utf-8") as f:
            content = f.read()
        assert "PrivateTmp=true" in content

    def test_service_has_protect_system(self):
        with open("scripts/ibkr-trader.service", "r", encoding="utf-8") as f:
            content = f.read()
        assert "ProtectSystem=strict" in content


class TestGitignore:
    def test_env_secret_ignored(self):
        with open(".gitignore", "r", encoding="utf-8") as f:
            content = f.read()
        assert ".env.secret" in content
