"""SQLAlchemy ORM models."""

from datetime import date

from sqlalchemy import Boolean, Date, Float, Integer, String
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


class FundDetailsModel(Base):
    """Persistent fund configuration — mirrors workbook Fund_Details sheet."""

    __tablename__ = "fund_details"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    include: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    strategy_type: Mapped[str | None] = mapped_column(String(100))
    return_type: Mapped[str | None] = mapped_column(String(20))
    fee_mode: Mapped[str | None] = mapped_column(String(50))
    fee_status: Mapped[str | None] = mapped_column(String(20))
    management_fee_pct: Mapped[float | None] = mapped_column(Float)
    performance_fee_pct: Mapped[float | None] = mapped_column(Float)
    hurdle_rate_pct: Mapped[float | None] = mapped_column(Float)
    high_water_mark: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    liquidity_notes: Mapped[str | None] = mapped_column(String(1000))
