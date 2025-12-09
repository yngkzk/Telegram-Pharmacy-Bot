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

    # ============================================================
    # 4. (NEW) SAVE PHARMACY REPORT (MAIN)
    # ============================================================
    async def save_apothecary_report(
            self,
            user: str,
            district: str,
            road: str,
            lpu: str,
            comment: str
    ) -> int:
        """
        Saves the main header for a pharmacy report.
        Returns the new Report ID.
        """
        self._ensure_conn()

        query = '''
            INSERT INTO apothecary_report
            (date, user, district, road, apothecary, commentary)
            VALUES (?, ?, ?, ?, ?, ?)
        '''

        date_value = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        async with self.conn.execute(
                query,
                (date_value, user, district, road, lpu, comment)
        ) as cursor:
            await self.conn.commit()
            logger.info(f"New Apothecary report saved. ID: {cursor.lastrowid}")
            return cursor.lastrowid

    # ============================================================
    # 5. (NEW) SAVE PHARMACY ITEMS (DETAILS)
    # ============================================================
    async def save_apothecary_preps(self, report_id: int, items: List[tuple]) -> None:
        """
        Saves the list of medications with quantities.

        :param report_id: ID of the main report
        :param items: A list of tuples: [("MedName", "Quantity"), ("MedName2", "Qty")]
        """
        self._ensure_conn()

        if not items:
            return

        # Prepare data for executemany
        # We ensure the structure matches: (report_id, prep_name, remaining/quantity)
        data = [(report_id, name, str(qty)) for name, qty in items]

        await self.conn.executemany(
            '''
            INSERT INTO apothecary_detailed_report (report_id, prep, remaining)
            VALUES (?, ?, ?)
            ''',
            data
        )
        await self.conn.commit()

    # ============================================================
    # 🔍 GET LAST REPORT FOR DOCTOR
    # ============================================================
    async def get_last_doctor_report(self, user: str, doc_name: str) -> Optional[Dict[str, Any]]:
        """
        Fetches the most recent report for a specific doctor by the current user.
        """
        self._ensure_conn()

        # 1. Find the latest report ID
        query = '''
            SELECT id, date, term, commentary 
            FROM main_reports 
            WHERE user = ? AND doc_name = ? 
            ORDER BY date DESC 
            LIMIT 1
        '''

        async with self.conn.execute(query, (user, doc_name)) as cursor:
            row = await cursor.fetchone()

        if not row:
            return None

        report_id = row["id"]

        # 2. Get the medications for this report
        async with self.conn.execute("SELECT prep FROM detailed_report WHERE report_id = ?", (report_id,)) as cursor:
            preps_rows = await cursor.fetchall()
            preps = [p["prep"] for p in preps_rows]

        return {
            "date": row["date"],
            "term": row["term"],
            "commentary": row["commentary"],
            "preps": preps
        }

    # ============================================================
    # 📊 EXPORT METHODS (FETCH ALL DATA)
    # ============================================================
    async def fetch_all_doctor_data(self):
        """Fetches joined Doctor reports + Medications"""
        self._ensure_conn()
        query = """
            SELECT 
                m.id, m.date, m.user, m.district, m.road, m.lpu, 
                m.doc_name, m.doc_spec, m.doc_num, m.term, m.commentary,
                d.prep
            FROM main_reports m
            LEFT JOIN detailed_report d ON m.id = d.report_id
            ORDER BY m.date DESC
        """
        async with self.conn.execute(query) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def fetch_all_apothecary_data(self):
        """Fetches joined Pharmacy reports + Items"""
        self._ensure_conn()
        # Note: 'apothecary' column in DB acts as LPU name
        query = """
            SELECT 
                a.id, a.date, a.user, a.district, a.road, a.apothecary as lpu_name, 
                a.commentary,
                ad.prep, ad.remaining
            FROM apothecary_report a
            LEFT JOIN apothecary_detailed_report ad ON a.id = ad.report_id
            ORDER BY a.date DESC
        """
        async with self.conn.execute(query) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]