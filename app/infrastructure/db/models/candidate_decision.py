# app/infrastructure/db/models/candidate_decision.py
"""SQLAlchemy model for candidate_decisions table."""
from typing import Optional

from sqlalchemy import Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.base import Base


class CandidateDecisionModel(Base):
    __tablename__ = "candidate_decisions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False)
    decision_date: Mapped[str] = mapped_column(Text, nullable=False)
    decision: Mapped[str] = mapped_column(String(20), nullable=False)
    price_at_decision: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    quant_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    feature_snapshot_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    llm_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    future_return_7d: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    future_return_30d: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    alpha_vs_spy_7d: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    alpha_vs_spy_30d: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    evaluated_7d_at: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    evaluated_30d_at: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
