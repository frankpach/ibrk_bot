# app/bootstrap/db_init.py
"""Bootstrap database tables and seed data on startup."""
from app.infrastructure.db.compat import init_db, init_control_settings


def bootstrap_db() -> None:
    """Initialize all DB tables and seed control_settings from environment."""
    init_db()
    init_control_settings()
