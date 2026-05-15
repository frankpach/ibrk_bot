# app/infrastructure/db/models/active_symbol.py
"""SQLAlchemy model for active_symbols table."""
from sqlalchemy import Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.base import Base


class ActiveSymbolModel(Base):
    __tablename__ = "active_symbols"

    symbol: Mapped[str] = mapped_column(String(20), primary_key=True)
    market_key: Mapped[str] = mapped_column(String(20), primary_key=True)
    session_date: Mapped[str] = mapped_column(Text, primary_key=True)
    score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    selected_at: Mapped[str] = mapped_column(Text, nullable=False)
