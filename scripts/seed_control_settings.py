#!/usr/bin/env python3
"""
Seed control_settings table with defaults from .env / settings.py.
Run once after deployment: python scripts/seed_control_settings.py
Safe to re-run — skips existing keys.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.config.settings import (
    OPENCODE_BIN, OPENCODE_MODEL, IB_HOST,
    MAX_POSITIONS, MAX_RISK_PCT, MIN_RISK_USD,
    MAX_POSITION_USD, CAPITAL_CAP,
)
from app.infrastructure.db.compat import seed_control_setting, init_db

init_db()

DEFAULTS = [
    # Risk
    ("max_positions",         str(MAX_POSITIONS),    False),
    ("max_risk_pct",          str(MAX_RISK_PCT),     False),
    ("min_risk_usd",          str(MIN_RISK_USD),     False),
    ("max_position_usd",      str(MAX_POSITION_USD), False),
    ("capital_cap",           str(CAPITAL_CAP),      False),
    # Infra
    ("ib_host",               IB_HOST,               False),
    ("opencode_bin",          OPENCODE_BIN,           False),
    ("opencode_model",        OPENCODE_MODEL,         False),
    # LLM per-task models
    ("llm_model_analysis",    OPENCODE_MODEL,         False),
    ("llm_model_signal",      OPENCODE_MODEL,         False),
    ("llm_model_postmortem",  OPENCODE_MODEL,         False),
]

for key, value, is_secret in DEFAULTS:
    if value:
        seed_control_setting(key, value, is_secret)
        print(f"  seeded: {key} = {value[:40]}")

print("Done.")
