# app/api/auth.py
from fastapi import Header, HTTPException


def require_control_key(x_control_key: str | None = Header(default=None)) -> None:
    """FastAPI dependency — rejects requests without a valid X-Control-Key header."""
    from app.config.settings import API_CONTROL_KEY
    if not API_CONTROL_KEY or not x_control_key or x_control_key != API_CONTROL_KEY:
        raise HTTPException(status_code=401, detail="Invalid or missing X-Control-Key")
