from datetime import datetime
from typing import List, Optional
from sqlalchemy import String, Integer, DateTime, Boolean, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .base import Base  # Импортируем твой базовый класс


# ============================================================
# 🏥 ОТЧЕТЫ ПО ВРАЧАМ (Main Reports)
# ============================================================

class MainReport(Base):
    __tablename__ = "main_reports"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user: Mapped[str] = mapped_column(String)
    district: Mapped[str] = mapped_column(String)
    road: Mapped[int] = mapped_column(Integer)
    lpu: Mapped[str] = mapped_column(String)

    doc_name: Mapped[str] = mapped_column(String)
    doc_spec: Mapped[str] = mapped_column(String)
    doc_num: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    term: Mapped[str] = mapped_column(String)
    commentary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    date: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    # 🔥 МАГИЯ СВЯЗЕЙ (One-to-Many)
    # Это позволяет нам делать selectinload(MainReport.preps) в репозитории
    preps: Mapped[List["DetailedReport"]] = relationship(
        "DetailedReport",
        back_populates="report",
        cascade="all, delete-orphan"  # Удалим отчет -> удалятся и препараты
    )


class DetailedReport(Base):
    __tablename__ = "detailed_report"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    # Связываем с главной таблицей через Foreign Key
    report_id: Mapped[int] = mapped_column(ForeignKey("main_reports.id", ondelete="CASCADE"))
    prep: Mapped[str] = mapped_column(String)

    # Обратная связь
    report: Mapped["MainReport"] = relationship("MainReport", back_populates="preps")


# ============================================================
# 🏪 ОТЧЕТЫ ПО АПТЕКАМ (Apothecary Reports)
# ============================================================

class ApothecaryReport(Base):
    __tablename__ = "apothecary_report"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user: Mapped[str] = mapped_column(String)
    district: Mapped[str] = mapped_column(String)
    road: Mapped[int] = mapped_column(Integer)
    apothecary: Mapped[str] = mapped_column(String)

    commentary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    date: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    # Связь с препаратами аптеки
    preps: Mapped[List["ApothecaryDetailedReport"]] = relationship(
        "ApothecaryDetailedReport",
        back_populates="report",
        cascade="all, delete-orphan"
    )


class ApothecaryDetailedReport(Base):
    __tablename__ = "apothecary_detailed_report"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    report_id: Mapped[int] = mapped_column(ForeignKey("apothecary_report.id", ondelete="CASCADE"))

    prep: Mapped[str] = mapped_column(String)
    request: Mapped[str] = mapped_column(String)  # В старой базе у тебя это была строка
    remaining: Mapped[str] = mapped_column(String)  # И это тоже строка

    report: Mapped["ApothecaryReport"] = relationship("ApothecaryReport", back_populates="preps")


# ============================================================
# 📋 ЗАДАЧИ И УВЕДОМЛЕНИЯ (Tasks)
# ============================================================

class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    text: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class UserTaskProgress(Base):
    __tablename__ = "user_task_progress"

    # Здесь user_id выступает как Primary Key, потому что у одного юзера только один прогресс
    user_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    last_task_id: Mapped[int] = mapped_column(Integer, default=0)