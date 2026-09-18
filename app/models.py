from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, Float, Integer, Date, ForeignKey
from datetime import date
from app.database import Base

class MutualFund(Base):
    __tablename__ = "mutual_funds"

    scheme_code: Mapped[str] = mapped_column(String(20), primary_key=True, index=True)
    scheme_name: Mapped[str] = mapped_column(String(255), nullable=False)

class Holding(Base):
    __tablename__ = "holdings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    scheme_code: Mapped[str] = mapped_column(ForeignKey("mutual_funds.scheme_code"), index=True)
    total_units: Mapped[float] = mapped_column(Float, nullable=False)
    average_nav: Mapped[float] = mapped_column(Float, nullable=False)
    invested_amount: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

class NAVHistory(Base):
    __tablename__ = "nav_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    scheme_code: Mapped[str] = mapped_column(ForeignKey("mutual_funds.scheme_code"), index=True)
    nav_date: Mapped[str] = mapped_column(String(20), index=True)
    nav_value: Mapped[float] = mapped_column(Float, nullable=False)