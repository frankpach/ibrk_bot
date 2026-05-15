# app/infrastructure/db/models/control_setting.py
"""SQLAlchemy model for control_settings table."""
from typing import Optional

from sqlalchemy import Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.base import Base


class ControlSettingModel(Base):
    __tablename__ = "control_settings"

    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[str] = mapped_column(Text, nullable=False)
    is_secret: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    requires_restart: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_by: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
