# app/infrastructure/db/models/news_cache.py
"""SQLAlchemy model for news_cache table."""
from typing import Optional

from sqlalchemy import Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.base import Base


class NewsCacheModel(Base):
    __tablename__ = "news_cache"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    symbol: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    headline: Mapped[str] = mapped_column(Text, nullable=False)
    provider: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    sentiment: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    article_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    published_at: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    fetched_at: Mapped[str] = mapped_column(Text, nullable=False)
