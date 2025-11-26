import aiosqlite
from typing import List, Dict, Any
from datetime import datetime


class ReportRepository:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.conn: aiosqlite.Connection | None = None

    async def connect(self):
        """Подключение к базе"""
        self.conn = await aiosqlite.connect(self.db_path)
        self.conn.row_factory = aiosqlite.Row
        await self.conn.execute("PRAGMA foreign_keys = ON;")

    async def close(self):
        if self.conn:
            await self.conn.close()

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

        query = '''
            INSERT INTO main_reports
            (date, user, district, road, lpu, doc_name, doc_spec, doc_num, term, commentary)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        '''

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
            return cursor.lastrowid

    # ============================================================
    # 2. СОХРАНЕНИЕ СПИСКА ПРЕПАРАТОВ
    # ============================================================
    async def save_preps(self, report_id: int, preps: List[str]) -> None:

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
    async def get_full_report(self, report_id: int) -> Dict[str, Any]:
        """Получает основной отчёт + список препаратов"""

        main_query = """
            SELECT *
            FROM main_reports
            WHERE id = ?
        """

        preps_query = """
            SELECT prep
            FROM detailed_report
            WHERE report_id = ?
        """

        main_row = await self.conn.execute(main_query, (report_id,))
        main_data = await main_row.fetchone()

        preps_row = await self.conn.execute(preps_query, (report_id,))
        preps_data = await preps_row.fetchall()

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
