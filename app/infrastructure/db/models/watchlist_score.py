# app/infrastructure/db/models/watchlist_score.py
"""SQLAlchemy model for watchlist_scores table."""
from sqlalchemy import Float, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.base import Base


class WatchlistScoreModel(Base):
    __tablename__ = "watchlist_scores"

    symbol: Mapped[str] = mapped_column(String(20), primary_key=True)
    signal_quality_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    admission_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    trade_history_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    watchlist_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    last_updated: Mapped[str] = mapped_column(Text, nullable=False)
