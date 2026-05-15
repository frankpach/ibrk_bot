# app/infrastructure/db/models/account_snapshot.py
"""SQLAlchemy model for account_snapshots table."""
from typing import Optional

from sqlalchemy import Float, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.base import Base


class AccountSnapshotModel(Base):
    __tablename__ = "account_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    date: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    net_liquidation: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    buying_power: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    daily_pnl_usd: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    daily_pnl_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    created_at: Mapped[str] = mapped_column(Text, nullable=False)
