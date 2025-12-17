import aiosqlite
from datetime import datetime
from typing import Optional, List, Any

from utils.text import pw
from utils.logger.logger_config import logger


class BotDB:
    def __init__(self, db_file: str):
        self.db_file = db_file
        self.conn: Optional[aiosqlite.Connection] = None

    async def connect(self):
        """Асинхронное подключение к базе"""
        try:
            self.conn = await aiosqlite.connect(self.db_file)
            await self.conn.execute("PRAGMA foreign_keys = ON;")
            self.conn.row_factory = aiosqlite.Row
            # logger.info(f"Connected to SQLite: {self.db_file}")
        except Exception as e:
            logger.critical(f"Connection failed for {self.db_file}: {e}")
            raise e

    async def close(self):
        """Закрытие соединения"""
        if self.conn:
            await self.conn.close()
            logger.info(f"Async DB connection closed for {self.db_file}")

    # ============================================================
    # 🛠 Вспомогательные методы (The Core Logic)
    # ============================================================

    def _ensure_conn(self):
        """Проверка соединения перед запросом"""
        if not self.conn:
            raise ConnectionError(f"Database {self.db_file} is not connected! Call .connect() first.")

    async def _fetchall(self, query: str, params: tuple = ()) -> List[aiosqlite.Row]:
        self._ensure_conn()
        async with self.conn.execute(query, params) as cursor:
            return await cursor.fetchall()

    async def _fetchone(self, query: str, params: tuple = ()) -> Optional[aiosqlite.Row]:
        self._ensure_conn()
        async with self.conn.execute(query, params) as cursor:
            return await cursor.fetchone()

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

    async def get_user_id(self, user_id: int) -> Optional[int]:
        row = await self._fetchone("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
        return row["user_id"] if row else None

    async def get_active_username(self, user_id: int) -> Optional[str]:
        # FIXED: Consistent Row access
        row = await self._fetchone(
            "SELECT user_name FROM users WHERE user_id = ? AND logged_in = 1",
            (user_id,)
        )
        return row["user_name"] if row else None

    async def get_user_list(self) -> List[str]:
        rows = await self._fetchall("SELECT user_name FROM users")
        return [row["user_name"] for row in rows]

    async def add_user(self, user_id: int, user_name: str, user_password: str, region: str):
        await self._execute("""
            INSERT INTO users (user_id, user_name, join_date, user_password, region, logged_in)
            VALUES (?, ?, ?, ?, ?, 1)
        """, (user_id, user_name, datetime.now(), user_password, region))

    async def is_logged_in(self, user_id: int, user_name: str) -> bool:
        row = await self._fetchone(
            "SELECT logged_in FROM users WHERE user_id = ? AND user_name = ?",
            (user_id, user_name)
        )
        return bool(row and row["logged_in"] == 1)

    async def check_password(self, username: str, password: str) -> bool:
        row = await self._fetchone("SELECT user_password FROM users WHERE user_name = ?", (username,))
        if not row:
            return False
        return pw.check_password(password, row["user_password"])

    async def set_logged_in(self, user_id: int, username: str, status: bool):
        # Convert bool to int (0/1) for SQLite
        status_int = 1 if status else 0
        await self._execute(
            "UPDATE users SET logged_in = ? WHERE user_id = ? AND user_name = ?",
            (status_int, user_id, username)
        )

    async def logout_user(self, user_id: int):
        await self._execute("UPDATE users SET logged_in = 0 WHERE user_id = ?", (user_id,))

    # ============================================================
    # 🏥 LPU (Medical Facilities)
    # ============================================================

    async def add_lpu(self, road_id: int, pharmacy_name: str, pharmacy_url: str):
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

    async def get_road_id_by_number(self, district_id: int, road_num: int) -> int:
        """Finds the unique road_id based on district and road number."""
        self._ensure_conn()
        row = await self._fetchone(
            "SELECT road_id FROM roads WHERE district_name = ? AND road_num = ?",
            (district_id, road_num)
        )
        return row['road_id'] if row else None

    # ============================================================
    # 💊 APOTHECARY
    # ============================================================

    async def add_apothecary_place(self, road_id: int, name: str, url: str):
        """
        Adds a new Pharmacy (Place) to the 'apothecary' table.
        """
        self._ensure_conn()  # Check connection

        await self._execute(
            "INSERT INTO apothecary (road_id, name, url) VALUES (?, ?, ?)",
            (road_id, name, url)
        )
        logger.info(f"Added Apothecary place: {name}")

    async def get_apothecary_list(self, district: str, road: int):
        return await self._fetchall("""
            SELECT a.id, a.name, a.url
            FROM apothecary AS a
            JOIN roads AS r ON r.road_id = a.road_id
            WHERE r.district_name = ? AND r.road_num = ?
            ORDER BY a.id
        """, (district, road))

    # ============================================================
    # 👨‍⚕️ ADD DOCTOR (With Spec ID Resolution)
    # ============================================================
    async def add_doc(self, lpu_id: int, name: str, spec_input: str, phone: str, birthdate: str):
        """
        Adds a doctor.
        Handles 'spec_input' which can be:
        1. A Main Spec ID (string of digits) -> Resolves to specs.spec_id
        2. A New Spec Name (text) -> Creates new entry in specs table
        """
        self._ensure_conn()

        real_spec_id = None

        # CASE 1: User selected from the list (It's a Main Spec ID)
        if str(spec_input).isdigit():
            main_spec_id = int(spec_input)

            # Step A: Check if this Main Spec already exists in 'specs' table
            row = await self._fetchone("SELECT spec_id FROM specs WHERE ms_id = ?", (main_spec_id,))

            if row:
                real_spec_id = row['spec_id']
            else:
                # Step B: If not, fetch the name from main_specs and create a new entry in specs
                ms_row = await self._fetchone("SELECT spec FROM main_specs WHERE main_spec_id = ?", (main_spec_id,))

                if ms_row:
                    spec_name = ms_row['spec']
                    # Insert into specs to generate a valid spec_id
                    async with self.conn.execute("INSERT INTO specs (ms_id, spec) VALUES (?, ?)",
                                                 (main_spec_id, spec_name)) as cursor:
                        real_spec_id = cursor.lastrowid
                    await self.conn.commit()
                else:
                    raise ValueError(f"Main Spec ID {main_spec_id} not found in DB!")

        # CASE 2: User typed a new specialty manually (Text)
        else:
            spec_name = spec_input.strip()

            # Check if this text already exists in 'specs'
            row = await self._fetchone("SELECT spec_id FROM specs WHERE spec LIKE ?", (spec_name,))

            if row:
                real_spec_id = row['spec_id']
            else:
                # Create completely new spec (No link to main_specs)
                async with self.conn.execute("INSERT INTO specs (spec, ms_id) VALUES (?, NULL)",
                                             (spec_name,)) as cursor:
                    real_spec_id = cursor.lastrowid
                await self.conn.commit()

        # Final Check
        if not real_spec_id:
            raise ValueError("Failed to resolve Specialty ID.")

        # Step 3: Finally Insert the Doctor
        await self._execute(
            "INSERT INTO doctors (lpu_id, doctor, spec_id, numb, birthdate) VALUES (?, ?, ?, ?, ?)",
            (lpu_id, name, real_spec_id, phone, birthdate)
        )

    async def get_doctor_name(self, doc_id: int) -> str:
        """Fetches the full name of the doctor by ID."""
        self._ensure_conn()
        # Table is 'doctors', column is 'doctor' (based on your schema)
        res = await self._fetchone("SELECT doctor FROM doctors WHERE id = ?", (doc_id,))
        return res["doctor"] if res else "Unknown Doctor"

    async def get_doctors(self, lpu_id: int):
        # Make sure there is NO "LIMIT" clause here
        sql = "SELECT * FROM doctors WHERE lpu_id = ?"
        return await self._fetchall(sql, (lpu_id,))

    async def get_doctors_list(self, lpu_id: int):
        return await self._fetchall("""
            SELECT d.id, d.doctor, s.spec, d.numb
            FROM doctors d
            JOIN specs s ON d.spec_id = s.spec
            WHERE d.lpu_id = ?
            ORDER BY d.id
        """, (lpu_id,))

    async def get_doc_stats(self, doc_id: int):
        return await self._fetchone("""
            SELECT ms.spec, d.numb
            FROM doctors d
            JOIN specs s ON d.spec_id = s.spec_id
            JOIN main_specs ms ON s.ms_id = ms.main_spec_id
            WHERE d.id = ?
        """, (doc_id,))

    # ============================================================
    # 📂 OTHER TABLES
    # ============================================================

    async def get_district_list(self):
        return await self._fetchall("SELECT id, name FROM districts")

    async def get_road_list(self):
        rows = await self._fetchall("SELECT DISTINCT road_num FROM roads")
        return [row["road_num"] for row in rows if row["road_num"] is not None]

    async def get_spec_list(self):
        return await self._fetchall("SELECT main_spec_id, spec FROM main_specs")

    async def get_prep_list(self):
        return await self._fetchall("SELECT id, prep FROM medication")

    # ============================================================
    # 🔍 LOOKUP METHODS (Get Name by ID)
    # ============================================================

    async def get_district_name(self, district_id: int) -> str:
        """Translates District ID -> District Name"""
        self._ensure_conn()
        # ⚠️ CHECK TABLE NAME: Assuming 'districts' and column 'name'
        res = await self._fetchone("SELECT name FROM districts WHERE id = ?", (district_id,))
        return res["name"] if res else "Unknown"