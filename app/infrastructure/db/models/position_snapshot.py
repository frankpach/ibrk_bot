# app/infrastructure/db/models/position_snapshot.py
"""SQLAlchemy model for position_snapshots table."""
from typing import Optional

from sqlalchemy import Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.base import Base


class PositionSnapshotModel(Base):
    __tablename__ = "position_snapshots"

    trade_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False)
    current_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    pnl_usd: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    pnl_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    updated_at: Mapped[str] = mapped_column(Text, nullable=False)
