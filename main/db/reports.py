import aiosqlite
from typing import List, Dict, Any, Optional
from datetime import datetime
from utils.logger.logger_config import logger


class ReportRepository:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.conn: Optional[aiosqlite.Connection] = None

    async def connect(self):
        """Подключение к базе"""
        try:
            self.conn = await aiosqlite.connect(self.db_path)
            self.conn.row_factory = aiosqlite.Row
            await self.conn.execute("PRAGMA foreign_keys = ON;")
            # logger.info(f"Report DB connected: {self.db_path}")
        except Exception as e:
            logger.critical(f"Failed to connect to Report DB: {e}")
            raise e

    async def close(self):
        if self.conn:
            await self.conn.close()
            logger.info("Report DB connection closed")

    def _ensure_conn(self):
        if not self.conn:
            raise ConnectionError("ReportDB is not connected!")

    # ============================================================
    # 1. СОХРАНЕНИЕ ОСНОВНОГО ОТЧЁТА
    # ============================================================
    async def save_main_report(
            self,
            user: str,
            district: str,
            road: str,
            lpu: str,
            doctor_name: str,
            doctor_spec: str,
            doctor_number: str,
            term: str,
            comment: str
    ) -> int:
        self._ensure_conn()

        query = '''
            INSERT INTO main_reports
            (date, user, district, road, lpu, doc_name, doc_spec, doc_num, term, commentary)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        '''

        # Using ISO format is safer for sorting
        date_value = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        async with self.conn.execute(
                query,
                (
                        date_value, user, district, road, lpu,
                        doctor_name, doctor_spec, doctor_number,
                        term, comment
                )
        ) as cursor:
            await self.conn.commit()
            logger.info(f"New report saved. ID: {cursor.lastrowid} by {user}")
            return cursor.lastrowid

    # ============================================================
    # 2. СОХРАНЕНИЕ СПИСКА ПРЕПАРАТОВ
    # ============================================================
    async def save_preps(self, report_id: int, preps: List[str]) -> None:
        self._ensure_conn()

        if not preps:
            return

        data = [(report_id, p) for p in preps]

        await self.conn.executemany(
            '''
            INSERT INTO detailed_report (report_id, prep)
            VALUES (?, ?)
            ''',
            data
        )
        await self.conn.commit()

    # ============================================================
    # 3. ПОЛУЧЕНИЕ ПОЛНОГО ОТЧЁТА
    # ============================================================
    async def get_full_report(self, report_id: int) -> Optional[Dict[str, Any]]:
        """
        Получает основной отчёт + список препаратов.
        Возвращает None, если отчёт не найден.
        """
        self._ensure_conn()

        main_query = "SELECT * FROM main_reports WHERE id = ?"
        preps_query = "SELECT prep FROM detailed_report WHERE report_id = ?"

        # 1. Get Main Info
        async with self.conn.execute(main_query, (report_id,)) as cursor:
            main_data = await cursor.fetchone()

        # SAFETY CHECK: If ID doesn't exist, return None immediately
        if not main_data:
            logger.warning(f"Requested report {report_id} not found.")
            return None

        # 2. Get Preps (only if main exists)
        async with self.conn.execute(preps_query, (report_id,)) as cursor:
            preps_data = await cursor.fetchall()

        return {
            "id": report_id,
            "date": main_data["date"],
            "user": main_data["user"],
            "district": main_data["district"],
            "road": main_data["road"],
            "lpu": main_data["lpu"],
            "doc_name": main_data["doc_name"],
            "doc_spec": main_data["doc_spec"],
            "doc_num": main_data["doc_num"],
            "term": main_data["term"],
            "commentary": main_data["commentary"],
            "preps": [p["prep"] for p in preps_data]
        }