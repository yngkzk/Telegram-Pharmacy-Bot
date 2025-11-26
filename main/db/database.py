import aiosqlite
from datetime import datetime
from utils.text import pw
from utils.logger.logger_config import logger


class BotDB:
    def __init__(self, db_file: str):
        self.db_file = db_file
        self.conn: aiosqlite.Connection | None = None

    async def connect(self):
        """Асинхронное подключение к базе"""
        self.conn = await aiosqlite.connect(self.db_file)
        await self.conn.execute("PRAGMA foreign_keys = ON;")
        self.conn.row_factory = aiosqlite.Row
        logger.info(f"Connected to async DB: {self.db_file}")

    async def close(self):
        """Закрытие соединения"""
        if self.conn:
            await self.conn.close()
            logger.info("Async DB connection closed")

    # ============================================================
    # Вспомогательные методы
    # ============================================================

    async def _fetchall(self, query: str, params: tuple = ()):
        async with self.conn.execute(query, params) as cursor:
            return await cursor.fetchall()

    async def _fetchone(self, query: str, params: tuple = ()):
        async with self.conn.execute(query, params) as cursor:
            return await cursor.fetchone()

    async def _execute(self, query: str, params: tuple = ()):
        await self.conn.execute(query, params)
        await self.conn.commit()

    # ============================================================
    # USERS
    # ============================================================

    async def user_exists(self, user_id: int) -> bool:
        result = await self._fetchone(
            "SELECT 1 FROM users WHERE user_id = ?",
            (user_id,)
        )
        return result is not None

    async def get_user_id(self, user_id: int) -> int | None:
        row = await self._fetchone(
            "SELECT user_id FROM users WHERE user_id = ?",
            (user_id,)
        )
        return row["user_id"] if row else None

    async def get_user_list(self):
        rows = await self._fetchall("SELECT user_name FROM users")
        return [row["user_name"] for row in rows]

    async def add_user(self, user_id, user_name, user_password, region):
        await self._execute("""
            INSERT INTO users (user_id, user_name, join_date, user_password, region, logged_in)
            VALUES (?, ?, ?, ?, ?, 1)
        """, (user_id, user_name, datetime.now(), user_password, region))

    async def is_logged_in(self, user_id: int) -> bool:
        row = await self._fetchone(
            "SELECT logged_in FROM users WHERE user_id = ?",
            (user_id,)
        )
        return row and row["logged_in"] == 1

    async def check_password(self, username: str, password: str) -> bool:
        row = await self._fetchone(
            "SELECT user_password FROM users WHERE user_name = ?",
            (username,)
        )
        if not row:
            return False
        return pw.check_password(password, row["user_password"])

    async def set_logged_in(self, username: str, status: bool):
        await self._execute(
            "UPDATE users SET logged_in = ? WHERE user_name = ?",
            (status, username)
        )

    async def logout_user(self, user_id):
        await self._execute(
            "UPDATE users SET logged_in = 0 WHERE user_id = ?",
            (user_id,)
        )

    # ============================================================
    # LPU
    # ============================================================

    async def add_lpu(self, road_id, pharmacy_name, pharmacy_url):
        await self._execute("""
            INSERT INTO lpu (road_id, pharmacy_name, pharmacy_url)
            VALUES (?, ?, ?)
        """, (road_id, pharmacy_name, pharmacy_url))

    async def get_lpu_list(self, district: str, road: int):
        return await self._fetchall("""
            SELECT l.lpu_id, l.pharmacy_name, l.pharmacy_url
            FROM lpu l
            JOIN roads r ON r.road_id = l.road_id
            WHERE r.district_name = ? AND r.road_num = ?
            ORDER BY l.pharmacy_name
        """, (district, road))

    # ============================================================
    # DOCTORS
    # ============================================================

    async def add_doc(self, lpu_id, doctor_name, spec_id, number, birthdate):
        await self._execute("""
            INSERT INTO doctors (lpu_id, doctor, spec_id, numb, birthdate)
            VALUES (?, ?, ?, ?, ?)
        """, (lpu_id, doctor_name, spec_id, number, birthdate))

    async def get_doctors_list(self, lpu_id: int):
        return await self._fetchall("""
            SELECT d.id, d.doctor, s.spec, d.numb
            FROM doctors d
            JOIN specs s ON d.spec_id = s.spec_id
            WHERE d.lpu_id = ?
            ORDER BY d.id
        """, (lpu_id,))

    async def get_doc_stats(self, doc_id: int):
        return await self._fetchone("""
            SELECT s.spec, d.numb
            FROM doctors d
            JOIN specs s ON d.spec_id = s.spec_id
            WHERE d.id = ?
        """, (doc_id,))

    # ============================================================
    # OTHER TABLES
    # ============================================================

    async def get_district_list(self):
        rows = await self._fetchall("SELECT id, name FROM districts")
        logger.info(f"District rows: {rows}")
        return rows

    async def get_road_list(self):
        rows = await self._fetchall("SELECT DISTINCT road_num FROM roads")
        road_list = [row["road_num"] for row in rows if row["road_num"] is not None]
        return road_list

    async def get_spec_list(self):
        return await self._fetchall(
            "SELECT main_spec_id, spec FROM main_specs"
        )

    async def get_prep_list(self):
        return await self._fetchall(
            "SELECT id, prep FROM medication"
        )