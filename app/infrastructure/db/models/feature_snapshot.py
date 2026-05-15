# app/infrastructure/db/models/feature_snapshot.py
"""SQLAlchemy model for feature_snapshots table."""
from typing import Optional

from sqlalchemy import Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.base import Base


class FeatureSnapshotModel(Base):
    __tablename__ = "feature_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    timestamp: Mapped[str] = mapped_column(Text, nullable=False)
    context: Mapped[str] = mapped_column(Text, nullable=False)
    rsi_14: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    macd_line: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    macd_signal: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    macd_crossover: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    atr_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    sma20: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    sma50: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    sma200: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    bollinger_upper: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    bollinger_lower: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    bollinger_position: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    vwap: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    volume_ratio_20d: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    hist_volatility_30d: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    impl_volatility: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    rs_vs_spy_30d: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    rs_vs_qqq_30d: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    feature_relevance_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True, default="{}")
    rsi_1h: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    volume_ratio_1h: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    weekly_trend: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
