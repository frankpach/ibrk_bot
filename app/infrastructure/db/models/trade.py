# app/infrastructure/db/models/trade.py
"""SQLAlchemy model for trades table."""
from datetime import datetime
from typing import Optional

from sqlalchemy import Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.base import Base


class TradeModel(Base):
    __tablename__ = "trades"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(10), nullable=False)
    quantity: Mapped[float] = mapped_column(Float, nullable=False)
    entry_price: Mapped[float] = mapped_column(Float, nullable=False)
    stop_loss_price: Mapped[float] = mapped_column(Float, nullable=False)
    take_profit_price: Mapped[float] = mapped_column(Float, nullable=False)
    stop_loss_pct: Mapped[float] = mapped_column(Float, nullable=False)
    take_profit_pct: Mapped[float] = mapped_column(Float, nullable=False)
    signal_strength: Mapped[str] = mapped_column(String(20), nullable=False)
    llm_justification: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="OPEN")
    exit_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    exit_reason: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    pnl_usd: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    pnl_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    opened_at: Mapped[str] = mapped_column(Text, nullable=False)
    closed_at: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    order_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    trade_status: Mapped[str] = mapped_column(String(20), nullable=False, default="PENDING")
    entry_fill_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    exit_fill_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    close_order_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    partial_exit_done: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    remaining_quantity: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    feature_snapshot_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
