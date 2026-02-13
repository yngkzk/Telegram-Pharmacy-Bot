import aiosqlite
from typing import List, Optional, Tuple
from pathlib import Path
from datetime import datetime
from utils.logger.logger_config import logger


class ReportRepository:
    def __init__(self, db_file: Path):
        self.db_file = db_file
        self.conn: Optional[aiosqlite.Connection] = None

    async def connect(self):
        """Подключается к БД и проверяет наличие таблиц задач."""
        if self.conn:
            return
        self.conn = await aiosqlite.connect(self.db_file)
        self.conn.row_factory = aiosqlite.Row
        await self.create_tasks_tables()
        logger.info(f"Connected to Reports DB: {self.db_file.name}")

    async def create_tasks_tables(self):
        """Создает таблицы для задач, если их нет."""
        await self.conn.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                text TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_active BOOLEAN DEFAULT 1
            )
        """)
        await self.conn.execute("""
            CREATE TABLE IF NOT EXISTS user_task_progress (
                user_id INTEGER PRIMARY KEY,
                last_task_id INTEGER
            )
        """)
        await self.conn.commit()

    async def close(self):
        if self.conn:
            await self.conn.close()
            self.conn = None

    def _ensure_conn(self):
        if not self.conn:
            raise ConnectionError("Reports DB is not connected. Call .connect() first.")

    # ============================================================
    # 📝 СОХРАНЕНИЕ ОТЧЕТОВ
    # ============================================================

    async def save_main_report(self, user: str, district: str, road: int, lpu: str,
                               doctor_name: str, doctor_spec: str, doctor_number: int,
                               term: str, comment: str) -> int:
        self._ensure_conn()
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        cursor = await self.conn.execute("""
            INSERT INTO main_reports (
                user, district, road, lpu, 
                doc_name, doc_spec, doc_num, 
                term, commentary, date
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (user, district, road, lpu, doctor_name, doctor_spec, doctor_number, term, comment, current_time))
        await self.conn.commit()
        return cursor.lastrowid

    async def save_preps(self, report_id: int, preps_list: List[str]):
        self._ensure_conn()
        data = [(report_id, prep_name) for prep_name in preps_list]
        await self.conn.executemany("INSERT INTO detailed_report (report_id, prep) VALUES (?, ?)", data)
        await self.conn.commit()

    async def save_apothecary_report(self, user: str, district: str, road: int, lpu: str, comment: str) -> int:
        self._ensure_conn()
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        cursor = await self.conn.execute("""
            INSERT INTO apothecary_report (
                user, district, road, apothecary, commentary, date
            ) VALUES (?, ?, ?, ?, ?, ?)
        """, (user, district, road, lpu, comment, current_time))
        await self.conn.commit()
        return cursor.lastrowid

    async def save_apothecary_preps(self, report_id: int, items: List[Tuple[str, int, int]]):
        """items = [(name, req, rem), ...]"""
        self._ensure_conn()
        data = [(report_id, item[0], str(item[1]), str(item[2])) for item in items]
        await self.conn.executemany("""
            INSERT INTO apothecary_detailed_report (report_id, prep, request, remaining) 
            VALUES (?, ?, ?, ?)
        """, data)
        await self.conn.commit()

    # ============================================================
    # 🕵️‍♂️ ПОЛУЧЕНИЕ ДАННЫХ
    # ============================================================

    async def get_last_doctor_report(self, user_name: str, doctor_name: str) -> Optional[dict]:
        self._ensure_conn()
        sql = """
            SELECT id, date, term, commentary
            FROM main_reports
            WHERE user = ? AND doc_name = ?
            ORDER BY date DESC LIMIT 1
        """
        try:
            async with self.conn.execute(sql, (user_name, doctor_name)) as cursor:
                report = await cursor.fetchone()

            if not report:
                return None

            async with self.conn.execute("SELECT prep FROM detailed_report WHERE report_id = ?", (report['id'],)) as cursor:
                prep_rows = await cursor.fetchall()
                preps = [r['prep'] for r in prep_rows]

            return {
                "date": str(report['date'])[:10],
                "term": report['term'],
                "commentary": report['commentary'],
                "preps": preps
            }
        except Exception as e:
            logger.error(f"Error fetching last report: {e}")
            return None

    # ============================================================
    # 📊 FETCH DATA (Для Excel и Фильтрации)
    # ============================================================

    async def fetch_filtered_doctor_data(
            self,
            start_date: str,
            end_date: str,
            user_name: Optional[str] = None
    ) -> List[dict]:
        self._ensure_conn()

        # SQL адаптирован под main_reports
        sql = """
            SELECT 
                r.id,
                r.date as created_at, 
                r.user as user_name,
                r.district,
                r.road,
                r.lpu,
                r.doc_name as doctor_name,
                r.doc_spec as doctor_spec,
                r.doc_num as doctor_number,
                r.term,
                r.commentary,
                GROUP_CONCAT(p.prep, ', ') as preps
            FROM main_reports r
            LEFT JOIN detailed_report p ON r.id = p.report_id
            WHERE date(r.date) BETWEEN date(?) AND date(?)
        """
        params = [start_date, end_date]

        if user_name and user_name != "all":
            sql += " AND r.user = ?"
            params.append(user_name)

        sql += " GROUP BY r.id ORDER BY r.date DESC"

        async with self.conn.execute(sql, tuple(params)) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def fetch_filtered_apothecary_data(
            self,
            start_date: str,
            end_date: str,
            user_name: Optional[str] = None
    ) -> List[dict]:
        self._ensure_conn()

        # SQL адаптирован под apothecary_report
        sql = """
            SELECT 
                r.id,
                r.date as created_at,
                r.user as user_name,
                r.district,
                r.road,
                r.apothecary as lpu,
                p.prep as prep_name,
                p.request as req_qty,
                p.remaining as rem_qty,
                r.commentary
            FROM apothecary_report r
            JOIN apothecary_detailed_report p ON r.id = p.report_id
            WHERE date(r.date) BETWEEN date(?) AND date(?)
        """
        params = [start_date, end_date]

        if user_name and user_name != "all":
            sql += " AND r.user = ?"
            params.append(user_name)

        sql += " ORDER BY r.date DESC"

        async with self.conn.execute(sql, tuple(params)) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    # ============================================================
    # 📋 TASKS (Задачи - без изменений, таблица tasks существует)
    # ============================================================

    async def add_task(self, text: str):
        self._ensure_conn()
        await self.conn.execute(
            "INSERT INTO tasks (text, created_at, is_active) VALUES (?, ?, 1)",
            (text, datetime.now())
        )
        await self.conn.commit()

    async def get_active_tasks(self) -> List[dict]:
        self._ensure_conn()
        # Проверяем, есть ли колонка is_active (на случай старой версии таблицы)
        try:
            async with self.conn.execute(
                    "SELECT id, text, created_at FROM tasks WHERE is_active = 1 ORDER BY id DESC LIMIT 5"
            ) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]
        except Exception:
            # Если таблицы нет или структура другая, вернем пустоту
            return []

    async def get_unread_count(self, user_id: int) -> int:
        self._ensure_conn()
        try:
            async with self.conn.execute(
                    "SELECT last_task_id FROM user_task_progress WHERE user_id = ?",
                    (user_id,)
            ) as cursor:
                row = await cursor.fetchone()
                last_seen_id = row['last_task_id'] if row else 0

            async with self.conn.execute(
                    "SELECT COUNT(*) FROM tasks WHERE is_active = 1 AND id > ?",
                    (last_seen_id,)
            ) as cursor:
                row = await cursor.fetchone()
                return row[0] if row else 0
        except Exception:
            return 0

    async def mark_all_as_read(self, user_id: int):
        self._ensure_conn()
        try:
            async with self.conn.execute("SELECT MAX(id) FROM tasks WHERE is_active = 1") as cursor:
                row = await cursor.fetchone()
                max_id = row[0] if row and row[0] else 0

            if max_id == 0:
                return

            await self.conn.execute("""
                INSERT OR REPLACE INTO user_task_progress (user_id, last_task_id)
                VALUES (?, ?)
            """, (user_id, max_id))
            await self.conn.commit()
        except Exception:
            pass