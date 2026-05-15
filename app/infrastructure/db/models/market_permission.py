# app/infrastructure/db/models/market_permission.py
"""SQLAlchemy model for market_permissions table."""
from sqlalchemy import Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.base import Base


class MarketPermissionModel(Base):
    __tablename__ = "market_permissions"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    label: Mapped[str] = mapped_column(Text, nullable=False)
    sec_type: Mapped[str] = mapped_column(String(20), nullable=False)
    available: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    valid_exchanges: Mapped[str] = mapped_column(Text, nullable=False, default="")
    checked_at: Mapped[str] = mapped_column(Text, nullable=False)
