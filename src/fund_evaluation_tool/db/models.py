"""SQLAlchemy ORM models."""

from datetime import date

from sqlalchemy import Date, Float, Integer, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Fund(Base):
    __tablename__ = "funds"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(String(500))


class FundReturn(Base):
    __tablename__ = "fund_returns"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    fund_id: Mapped[int] = mapped_column(Integer, nullable=False)
    period_date: Mapped[date] = mapped_column(Date, nullable=False)
    return_value: Mapped[float] = mapped_column(Float, nullable=False)
