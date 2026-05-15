# app/infrastructure/db/models/signal.py
"""SQLAlchemy model for signals table."""
from typing import Optional

from sqlalchemy import Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.base import Base


class SignalModel(Base):
    __tablename__ = "signals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    strength: Mapped[str] = mapped_column(String(20), nullable=False)
    rsi: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    macd: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    volume_ratio: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    extra_indicators: Mapped[Optional[str]] = mapped_column(Text, nullable=True, default="{}")
    created_at: Mapped[str] = mapped_column(Text, nullable=False)
    processed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
