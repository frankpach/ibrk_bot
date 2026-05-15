# app/infrastructure/db/models/decision.py
"""SQLAlchemy model for decisions table."""
from typing import Optional

from sqlalchemy import Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.base import Base


class DecisionModel(Base):
    __tablename__ = "decisions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    signal_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False)
    llm_model: Mapped[str] = mapped_column(String(50), nullable=False)
    prompt_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    response: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    action: Mapped[str] = mapped_column(String(20), nullable=False)
    stop_loss_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    take_profit_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    created_at: Mapped[str] = mapped_column(Text, nullable=False)
