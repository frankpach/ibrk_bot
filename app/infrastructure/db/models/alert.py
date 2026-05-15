# app/infrastructure/db/models/alert.py
"""SQLAlchemy model for alerts table."""
from typing import Optional

from sqlalchemy import Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.base import Base


class AlertModel(Base):
    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False)
    threshold_pct: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[str] = mapped_column(Text, nullable=False)
    triggered_at: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
