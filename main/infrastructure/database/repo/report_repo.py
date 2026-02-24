from typing import List, Optional, Tuple
from datetime import datetime
from sqlalchemy import select, func, and_, desc
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from utils.logger.logger_config import logger

# Предполагаемые импорты твоих новых моделей (названия могут чуть отличаться)
from infrastructure.database.models.reports import (
    MainReport, DetailedReport,
    ApothecaryReport, ApothecaryDetailedReport,
    Task, UserTaskProgress
)


class ReportRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    # ============================================================
    # 📝 СОХРАНЕНИЕ ОТЧЕТОВ (WRITE)
    # ============================================================

    async def save_main_report(
            self, user: str, district: str, road: int, lpu: str,
            doctor_name: str, doctor_spec: str, doctor_number: str,
            term: str, comment: str
    ) -> MainReport:
        """Сохраняет основной отчет и возвращает объект отчета"""
        new_report = MainReport(
            user=user, district=district, road=road, lpu=lpu,
            doc_name=doctor_name, doc_spec=doctor_spec, doc_num=doctor_number,
            term=term, commentary=comment, date=datetime.now()
        )
        self.session.add(new_report)
        await self.session.commit()
        await self.session.refresh(new_report)  # Чтобы получить ID
        return new_report

    async def save_preps(self, report_id: int, preps_list: List[str]):
        """Массовое сохранение препаратов к отчету"""
        detailed_records = [
            DetailedReport(report_id=report_id, prep=prep_name)
            for prep_name in preps_list
        ]
        self.session.add_all(detailed_records)
        await self.session.commit()

    async def save_apothecary_report(
            self, user: str, district: str, road: int, lpu: str, comment: str
    ) -> ApothecaryReport:
        new_report = ApothecaryReport(
            user=user, district=district, road=road, apothecary=lpu,
            commentary=comment, date=datetime.now()
        )
        self.session.add(new_report)
        await self.session.commit()
        await self.session.refresh(new_report)
        return new_report

    async def save_apothecary_preps(self, report_id: int, items: List[Tuple[str, int, int]]):
        """items = [(name, req, rem), ...]"""
        detailed_records = [
            ApothecaryDetailedReport(
                report_id=report_id, prep=item[0], request=str(item[1]), remaining=str(item[2])
            ) for item in items
        ]
        self.session.add_all(detailed_records)
        await self.session.commit()

    # ============================================================
    # 🕵️‍♂️ ПОЛУЧЕНИЕ ДАННЫХ (READ)
    # ============================================================

    async def get_last_doctor_report(self, user_name: str, doctor_name: str) -> Optional[dict]:
        """Получает последний отчет по врачу вместе со списком препаратов"""
        # Используем selectinload для автоматической подгрузки препаратов (One-to-Many)
        stmt = (
            select(MainReport)
            .options(selectinload(MainReport.preps))  # Требует relationship в модели!
            .where(
                MainReport.user == user_name,
                MainReport.doc_name == doctor_name
            )
            .order_by(desc(MainReport.date))
            .limit(1)
        )
        result = await self.session.execute(stmt)
        report = result.scalar_one_or_none()

        if not report:
            return None

        # Собираем красивый словарь для хэндлера
        return {
            "date": report.date.strftime("%Y-%m-%d"),
            "term": report.term,
            "commentary": report.commentary,
            "preps": [p.prep for p in report.preps] if hasattr(report, 'preps') else []
        }

    # ============================================================
    # 📊 FETCH DATA (Для Excel и Фильтрации)
    # ============================================================

    async def fetch_filtered_doctor_data(
            self, start_date: str, end_date: str, user_name: Optional[str] = None
    ) -> List[dict]:
        """Выгрузка данных для Excel с жадной загрузкой препаратов"""

        # Конвертируем строки в объекты date для надежного сравнения
        s_date = datetime.strptime(start_date, "%Y-%m-%d").date()
        e_date = datetime.strptime(end_date, "%Y-%m-%d").date()

        stmt = select(MainReport).options(selectinload(MainReport.preps))

        # Фильтруем по дате (приводим datetime из базы к date)
        conditions = [func.date(MainReport.date).between(s_date, e_date)]

        if user_name and user_name != "all":
            conditions.append(MainReport.user == user_name)

        stmt = stmt.where(and_(*conditions)).order_by(desc(MainReport.date))

        result = await self.session.execute(stmt)
        reports = result.scalars().all()

        # Форматируем данные в Python, а не через хаки SQL
        return [{
            "id": r.id,
            "created_at": r.date,
            "user_name": r.user,
            "district": r.district,
            "road": r.road,
            "lpu": r.lpu,
            "doctor_name": r.doc_name,
            "doctor_spec": r.doc_spec,
            "doctor_number": r.doc_num,
            "term": r.term,
            "commentary": r.commentary,
            "preps": ", ".join([p.prep for p in r.preps]) if r.preps else ""
        } for r in reports]

    async def fetch_filtered_apothecary_data(
            self, start_date: str, end_date: str, user_name: Optional[str] = None
    ) -> List[dict]:
        s_date = datetime.strptime(start_date, "%Y-%m-%d").date()
        e_date = datetime.strptime(end_date, "%Y-%m-%d").date()

        stmt = select(ApothecaryReport).options(selectinload(ApothecaryReport.preps))

        conditions = [func.date(ApothecaryReport.date).between(s_date, e_date)]
        if user_name and user_name != "all":
            conditions.append(ApothecaryReport.user == user_name)

        stmt = stmt.where(and_(*conditions)).order_by(desc(ApothecaryReport.date))

        result = await self.session.execute(stmt)
        reports = result.scalars().all()

        output = []
        for r in reports:
            # Для аптек у нас препараты хранятся с количеством (req_qty, rem_qty)
            # Разворачиваем их в плоский список словарей, как ожидает генератор Excel
            for p in r.preps:
                output.append({
                    "id": r.id,
                    "created_at": r.date,
                    "user_name": r.user,
                    "district": r.district,
                    "road": r.road,
                    "lpu": r.apothecary,
                    "prep_name": p.prep,
                    "req_qty": p.request,
                    "rem_qty": p.remaining,
                    "commentary": r.commentary
                })
        return output

    # ============================================================
    # 📋 TASKS (Задачи)
    # ============================================================

    async def add_task(self, text: str):
        new_task = Task(text=text, is_active=True)
        self.session.add(new_task)
        await self.session.commit()

    async def get_active_tasks(self) -> List[dict]:
        stmt = select(Task).where(Task.is_active == True).order_by(desc(Task.id)).limit(5)
        result = await self.session.execute(stmt)
        tasks = result.scalars().all()
        return [{"id": t.id, "text": t.text, "created_at": t.created_at} for t in tasks]

    async def get_unread_count(self, user_id: int) -> int:
        """Считает количество новых (непрочитанных) задач для пользователя"""
        try:
            # 1. Узнаем ID последней прочитанной задачи
            stmt_progress = select(UserTaskProgress.last_task_id).where(UserTaskProgress.user_id == user_id)
            result_progress = await self.session.execute(stmt_progress)
            last_seen_id = result_progress.scalar_one_or_none() or 0

            # 2. Считаем все активные задачи, ID которых больше прочитанного
            stmt_count = select(func.count()).select_from(Task).where(
                Task.is_active == True,
                Task.id > last_seen_id
            )
            result_count = await self.session.execute(stmt_count)
            return result_count.scalar() or 0
        except Exception as e:
            logger.error(f"Error getting unread count: {e}")
            return 0

    async def mark_all_as_read(self, user_id: int):
        """Отмечает все текущие задачи как прочитанные (Upsert)"""
        try:
            # 1. Находим максимальный ID среди активных задач
            stmt_max = select(func.max(Task.id)).where(Task.is_active == True)
            result_max = await self.session.execute(stmt_max)
            max_id = result_max.scalar_one_or_none() or 0

            if max_id == 0:
                return

            # 2. Обновляем или создаем запись прогресса (аналог INSERT OR REPLACE)
            progress = UserTaskProgress(user_id=user_id, last_task_id=max_id)
            await self.session.merge(progress)
            await self.session.commit()
        except Exception as e:
            logger.error(f"Error marking tasks as read: {e}")