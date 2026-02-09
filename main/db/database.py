import aiosqlite
from typing import Optional, List, Union
from pathlib import Path
from datetime import datetime
from utils.logger.logger_config import logger
from utils.text import pw

class BotDB:
    def __init__(self, db_file: Path):
        self.db_file = db_file
        self.conn: Optional[aiosqlite.Connection] = None

    async def connect(self):
        try:
            self.conn = await aiosqlite.connect(self.db_file)
            self.conn.row_factory = aiosqlite.Row
            await self.conn.execute("PRAGMA foreign_keys = ON;")
            logger.info(f"Connected to SQLite: {self.db_file.name}")
        except Exception as e:
            logger.critical(f"Connection failed for {self.db_file}: {e}")
            raise

    async def close(self):
        if self.conn:
            await self.conn.close()
            logger.info(f"DB connection closed: {self.db_file.name}")

    def _ensure_conn(self):
        if not self.conn:
            raise ConnectionError(f"Database {self.db_file} is not connected! Call .connect() first.")

    # --- CRUD Helpers ---

    async def _fetchone(self, query: str, params: tuple = ()) -> Optional[aiosqlite.Row]:
        self._ensure_conn()
        async with self.conn.execute(query, params) as cursor:
            return await cursor.fetchone()

    async def _fetchall(self, query: str, params: tuple = ()) -> List[aiosqlite.Row]:
        self._ensure_conn()
        async with self.conn.execute(query, params) as cursor:
            return await cursor.fetchall()

    async def _execute(self, query: str, params: tuple = ()) -> None:
        self._ensure_conn()
        await self.conn.execute(query, params)
        await self.conn.commit()

    # ============================================================
    # 👤 USERS
    # ============================================================

    async def user_exists(self, user_id: int) -> bool:
        result = await self._fetchone("SELECT 1 FROM users WHERE user_id = ?", (user_id,))
        return result is not None

    async def get_active_username(self, user_id: int) -> Optional[str]:
        row = await self._fetchone(
            "SELECT user_name FROM users WHERE user_id = ? AND logged_in = 1",
            (user_id,)
        )
        return row["user_name"] if row else None

    async def get_user_list(self) -> List[str]:
        rows = await self._fetchall("SELECT user_name FROM users WHERE is_approved = 1")
        return [row["user_name"] for row in rows]

    async def add_user(self, user_id: int, user_name: str, user_password: str, region: str):
        await self._execute("""
            INSERT INTO users (user_id, user_name, join_date, user_password, region, logged_in, is_approved)
            VALUES (?, ?, ?, ?, ?, 1, 0)
        """, (user_id, user_name, datetime.now(), user_password, region))

    async def check_password(self, username: str, password: str) -> bool:
        row = await self._fetchone("SELECT user_password FROM users WHERE user_name = ?", (username,))
        if not row:
            return False
        return pw.check_password(password, row["user_password"])

    async def set_logged_in(self, user_id: int, username: str, status: bool):
        status_int = 1 if status else 0
        await self._execute(
            "UPDATE users SET logged_in = ? WHERE user_id = ? AND user_name = ?",
            (status_int, user_id, username)
        )

    async def logout_user(self, user_id: int):
        await self._execute("UPDATE users SET logged_in = 0 WHERE user_id = ?", (user_id,))

    # ============================================================
    # 🏥 LPU (Больницы)
    # ============================================================

    async def add_lpu(self, road_id: int, pharmacy_name: str, pharmacy_url: str):
        await self._execute("""
            INSERT INTO lpu (road_id, pharmacy_name, pharmacy_url)
            VALUES (?, ?, ?)
        """, (road_id, pharmacy_name, pharmacy_url))

    async def get_lpu_list(self, district: str, road: int) -> List[dict]:
        # ВОЗВРАЩАЕМ СТАРЫЕ КЛЮЧИ (pharmacy_name), но добавляем id для удобства
        rows = await self._fetchall("""
            SELECT l.lpu_id, l.lpu_id as id, l.pharmacy_name, l.pharmacy_url
            FROM lpu l
            JOIN roads r ON r.road_id = l.road_id
            WHERE r.district_name = ? AND r.road_num = ?
            ORDER BY l.pharmacy_name
        """, (district, road))
        return [dict(row) for row in rows]

    async def get_road_id_by_number(self, district_id: Union[str, int], road_num: int) -> int:
        row = await self._fetchone(
            "SELECT road_id FROM roads WHERE district_name = ? AND road_num = ?",
            (district_id, road_num)
        )
        return row['road_id'] if row else None

    # ============================================================
    # 💊 APOTHECARY (Аптеки)
    # ============================================================

    async def add_apothecary_place(self, road_id: int, name: str, url: str):
        await self._execute(
            "INSERT INTO apothecary (road_id, name, url) VALUES (?, ?, ?)",
            (road_id, name, url)
        )

    async def get_apothecary_list(self, district: str, road: int) -> List[dict]:
        # Возвращаем id, name, url (как и было в оригинале)
        rows = await self._fetchall("""
            SELECT a.id, a.name, a.url
            FROM apothecary AS a
            JOIN roads AS r ON r.road_id = a.road_id
            WHERE r.district_name = ? AND r.road_num = ?
            ORDER BY a.id
        """, (district, road))
        return [dict(row) for row in rows]

    # ============================================================
    # 👨‍⚕️ DOCTORS (Врачи)
    # ============================================================

    async def add_doc(self, lpu_id: int, name: str, spec_input: str, phone: str, birthdate: str):
        self._ensure_conn()
        real_spec_id = None

        if str(spec_input).isdigit():
            main_spec_id = int(spec_input)
            row = await self._fetchone("SELECT spec_id FROM specs WHERE ms_id = ?", (main_spec_id,))
            if row:
                real_spec_id = row['spec_id']
            else:
                ms_row = await self._fetchone("SELECT spec FROM main_specs WHERE main_spec_id = ?", (main_spec_id,))
                if ms_row:
                    spec_name = ms_row['spec']
                    async with self.conn.execute("INSERT INTO specs (ms_id, spec) VALUES (?, ?)", (main_spec_id, spec_name)) as cursor:
                        real_spec_id = cursor.lastrowid
                    await self.conn.commit()
        else:
            spec_name = spec_input.strip()
            row = await self._fetchone("SELECT spec_id FROM specs WHERE spec LIKE ?", (spec_name,))
            if row:
                real_spec_id = row['spec_id']
            else:
                async with self.conn.execute("INSERT INTO specs (spec, ms_id) VALUES (?, NULL)", (spec_name,)) as cursor:
                    real_spec_id = cursor.lastrowid
                await self.conn.commit()

        if not real_spec_id:
            raise ValueError("Ошибка: не удалось определить ID специальности.")

        await self._execute(
            "INSERT INTO doctors (lpu_id, doctor, spec_id, numb, birthdate) VALUES (?, ?, ?, ?, ?)",
            (lpu_id, name, real_spec_id, phone, birthdate)
        )

    async def get_doctor_name(self, doc_id: int) -> str:
        res = await self._fetchone("SELECT doctor FROM doctors WHERE id = ?", (doc_id,))
        return res["doctor"] if res else "Unknown Doctor"

    async def get_doctors(self, lpu_id: int) -> List[dict]:
        """
        ВОЗВРАЩАЕМ 'doctor' ЧТОБЫ ИЗБЕЖАТЬ KeyError!
        """
        rows = await self._fetchall("SELECT id, doctor FROM doctors WHERE lpu_id = ?", (lpu_id,))
        return [dict(row) for row in rows]

    async def get_doc_stats(self, doc_id: int) -> Optional[dict]:
        row = await self._fetchone("""
            SELECT ms.spec, d.numb
            FROM doctors d
            JOIN specs s ON d.spec_id = s.spec_id
            JOIN main_specs ms ON s.ms_id = ms.main_spec_id
            WHERE d.id = ?
        """, (doc_id,))
        return dict(row) if row else None

    # ============================================================
    # 📂 СПРАВОЧНИКИ
    # ============================================================

    async def get_district_list(self) -> List[dict]:
        rows = await self._fetchall("SELECT id, name FROM districts")
        return [dict(row) for row in rows]

    async def get_road_list(self) -> List[dict]:
        """Возвращаем и id, и name, чтобы любая клавиатура поняла"""
        rows = await self._fetchall("SELECT DISTINCT road_num FROM roads WHERE road_num IS NOT NULL ORDER BY road_num")
        return [{"id": row["road_num"], "name": str(row["road_num"])} for row in rows]

    async def get_spec_list(self) -> List[dict]:
        # Возвращаем 'spec' как раньше
        rows = await self._fetchall("SELECT main_spec_id as id, spec FROM main_specs")
        return [dict(row) for row in rows]

    async def get_prep_list(self) -> List[dict]:
        # Возвращаем 'prep' как раньше
        rows = await self._fetchall("SELECT id, prep FROM medication")
        return [dict(row) for row in rows]

    # ============================================================
    # 🔍 LOOKUP
    # ============================================================

    async def get_district_name(self, district_id: Union[int, str]) -> str:
        row = await self._fetchone("SELECT name FROM districts WHERE id = ?", (district_id,))
        return row["name"] if row else str(district_id)

    async def get_road_name(self, road_id: int) -> str:
        row = await self._fetchone("SELECT road_num FROM roads WHERE road_id = ?", (road_id,))
        if row:
             return f"Маршрут {row['road_num']}"
        return f"Маршрут {road_id}"

    # ============================================================
    # 👮 MODERATION
    # ============================================================

    async def get_pending_users(self) -> List[dict]:
        rows = await self._fetchall("SELECT user_id, user_name, region FROM users WHERE is_approved = 0")
        return [dict(row) for row in rows]

    async def approve_user(self, user_id: int):
        await self._execute("UPDATE users SET is_approved = 1 WHERE user_id = ?", (user_id,))

    async def delete_user(self, user_id: int):
        await self._execute("DELETE FROM users WHERE user_id = ?", (user_id,))

    async def is_user_approved(self, user_id: int) -> Optional[bool]:
        row = await self._fetchone("SELECT is_approved FROM users WHERE user_id = ?", (user_id,))
        if row is None:
            return None
        return bool(row["is_approved"])