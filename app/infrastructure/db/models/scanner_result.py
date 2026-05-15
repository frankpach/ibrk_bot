# app/infrastructure/db/models/scanner_result.py
"""SQLAlchemy model for scanner_results table."""
from typing import Optional

from sqlalchemy import Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.base import Base


class ScannerResultModel(Base):
    __tablename__ = "scanner_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    scan_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    change_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    volume_ratio: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    extra_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True, default="{}")
    fetched_at: Mapped[str] = mapped_column(Text, nullable=False)
