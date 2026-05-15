# app/infrastructure/db/models/daily_watchlist.py
"""SQLAlchemy model for daily_watchlist table."""
from typing import Optional

from sqlalchemy import Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.base import Base


class DailyWatchlistModel(Base):
    __tablename__ = "daily_watchlist"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    date: Mapped[str] = mapped_column(Text, nullable=False)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False)
    score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    signal_strength: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    change_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    volume_ratio: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    alerted: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    added_at: Mapped[str] = mapped_column(Text, nullable=False)
