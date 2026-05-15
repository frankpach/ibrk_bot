# app/interfaces/api/app.py
"""FastAPI application — currently delegates legacy endpoints via app.api.main.
Route files under app/interfaces/api/routes/ are staged for Issue 004+ migration.
"""
import os

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

app = FastAPI(title="IBKR AI Trader API")

_ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "")
allow_origins = [o.strip() for o in _ALLOWED_ORIGINS.split(",") if o.strip()] or ["*"]
if os.getenv("RESTRICT_CORS", "false").lower() == "true":
    allow_origins = [o.strip() for o in _ALLOWED_ORIGINS.split(",") if o.strip()]
    if not allow_origins:
        allow_origins = []

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["X-Control-Key", "X-Admin-Key", "Content-Type"],
)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    """Add security headers to every response."""
    response: Response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response
