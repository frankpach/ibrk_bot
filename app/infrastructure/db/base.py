# app/infrastructure/db/base.py
"""SQLAlchemy declarative base for all ORM models."""
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
