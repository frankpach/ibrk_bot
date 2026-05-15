# app/infrastructure/db/models/symbol_config.py
"""SQLAlchemy model for symbol_config table."""
from typing import Optional

from sqlalchemy import Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.base import Base


class SymbolConfigModel(Base):
    __tablename__ = "symbol_config"

    symbol: Mapped[str] = mapped_column(String(20), primary_key=True)
    extra_indicators: Mapped[Optional[str]] = mapped_column(Text, nullable=True, default="[]")
    approved: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    proposed_by: Mapped[str] = mapped_column(String(50), nullable=False, default="human")
    created_at: Mapped[str] = mapped_column(Text, nullable=False)
    sec_type: Mapped[str] = mapped_column(String(20), nullable=False, default="STK")
    exchange: Mapped[str] = mapped_column(String(50), nullable=False, default="SMART")
    currency: Mapped[str] = mapped_column(String(10), nullable=False, default="USD")
    liquid_hours: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    market_key: Mapped[str] = mapped_column(String(20), nullable=False, default="STK_US")
