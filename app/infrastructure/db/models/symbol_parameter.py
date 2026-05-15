# app/infrastructure/db/models/symbol_parameter.py
"""SQLAlchemy model for symbol_parameters table."""
from typing import Optional

from sqlalchemy import Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.base import Base


class SymbolParameterModel(Base):
    __tablename__ = "symbol_parameters"

    symbol: Mapped[str] = mapped_column(String(20), primary_key=True)
    stop_loss_pct: Mapped[float] = mapped_column(Float, nullable=False, default=0.025)
    take_profit_pct: Mapped[float] = mapped_column(Float, nullable=False, default=0.06)
    min_profit_pct: Mapped[float] = mapped_column(Float, nullable=False, default=0.01)
    momentum_mult: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    trend_mult: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    volume_mult: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    volatility_mult: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    portfolio_fit_mult: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    sentiment_mult: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    trade_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    previous_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    updated_at: Mapped[str] = mapped_column(Text, nullable=False)
    backtest_calibrated: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    backtest_calibrated_at: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    backtest_profit_factor: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
