import sqlite3

from datetime import datetime
from utils.text import pw
from utils.logger.logger_config import logger


class BotDB:

    def __init__(self, db_file):
        self.conn = sqlite3.connect(db_file)
        self.cursor = self.conn.cursor()

    def user_exists(self, user_id):
        """Проверка на наличие данного пользователя"""
        result = self.cursor.execute("SELECT `user_id` FROM `users` WHERE `user_id` = ?", (user_id,))
        return bool(len(result.fetchall()))

    def get_user_id(self, user_id):
        """Получаем id юзера в базе по его user_id в телеграмме"""
        result = self.cursor.execute("SELECT `user_id` FROM `users` WHERE `user_id` = ?", (user_id,))
        return result.fetchone()[0]

    def get_user_list(self):
        """Возвращаем список пользователей"""
        db_user_list = self.cursor.execute("SELECT `user_name` FROM `users`")
        result = db_user_list.fetchall()
        user_list = []
        for i in range(len(result)):
            converted = result[i]
            user_list.append(str(converted)[2:-3])
        return user_list

    def add_user(self, user_id, user_name, user_password, region):
        """Добавляем юзера в БД"""
        self.cursor.execute("INSERT INTO `users` (`user_id`, `user_name`, `join_date`, `user_password`, `region`, `logged_in`) "
                            "VALUES (?, ?, ?, ?, ?, ?)",
                            (user_id, user_name, datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                             user_password, region, 1))
        return self.conn.commit()

    def add_lpu(self, road_id, pharmacy_name, pharmacy_url):
        """Добавляем новое ЛПУ в БД"""
        self.cursor.execute("INSERT INTO `lpu` (`road_id`, `pharmacy_name`, `pharmacy_url`)"
                            "VALUES (?, ?, ?)",
                            (road_id, pharmacy_name, pharmacy_url))
        return self.conn.commit()

    def add_doc(self, lpu_id, doctor_name, spec_id, number):
        """Добавляем нового врача в БД"""
        self.cursor.execute("INSERT INTO `doctors` (`lpu_id`, `doctor`, `spec_id`, `numb`)"
                            "VALUES (?, ?, ?, ?)",
                            (lpu_id, doctor_name, spec_id, number))
        return self.conn.commit()

    def is_logged_in(self, user_id: int) -> bool:
        """
        Проверяет, вошёл ли пользователь в систему.
        Возвращает True, если logged_in = 1
        """
        result = self.cursor.execute(
            "SELECT logged_in FROM users WHERE user_id = ?",
            (user_id,)
        ).fetchone()
        return bool(result and result[0] == 1)

    def check_password(self, username: str, password: str) -> bool:
        user = self.cursor.execute("SELECT `user_password` FROM `users` WHERE user_name = ?", (username,)).fetchone()
        hashed = user[0]
        return pw.check_password(password, hashed)

    def set_logged_in(self, username: str, status: bool):
        self.cursor.execute("UPDATE `users` SET logged_in = ? WHERE user_name = ?", (status, username))
        self.conn.commit()

    def logout_user(self, user_id):
        self.cursor.execute("UPDATE `users` SET `logged_in` = 0 WHERE user_id = ?", (user_id,))
        self.conn.commit()

    def get_district_list(self):
        """Возвращаем список районов"""
        db_district_list = self.cursor.execute("SELECT DISTINCT `district_name` FROM `roads`")
        result = db_district_list.fetchall()
        logger.info(f"Результат в db.py - {result}")
        district_list = []
        for i in range(len(result)):
            converted = result[i]
            district_list.append(str(converted)[2:-3])
        return district_list

    def get_road_list(self):
        """Возвращаем список маршрутов как список int"""
        db_road_list = self.cursor.execute("SELECT DISTINCT `road_num` FROM `roads`")
        result = db_road_list.fetchall()

        # result = [(1,), (2,), (3,), ...]
        road_list = [int(row[0]) for row in result if row[0] is not None]

        logger.info(f"Результат в db.py - {result}")
        logger.info(f"road_list - {road_list}")
        return road_list

    def get_lpu_list(self, district: str, road: int):
        """
        Возвращает список ЛПУ (аптек) в указанном районе и маршруте.
        :param district: Название района
        :param road: Номер маршрута
        """

        query = """
            SELECT l.lpu_id, l.pharmacy_name, l.pharmacy_url
            FROM lpu AS l
            JOIN roads AS r ON r.road_id = l.road_id
            WHERE r.district_name = ? AND r.road_num = ?
            ORDER BY l.pharmacy_name
        """
        result = self.cursor.execute(query, (district, road)).fetchall()

        return result

    def get_doctors_list(self, lpu: str):
        """
        Возвращает список Врачей в указанном ЛПУ.
        :param lpu: Название ЛПУ
        """

        query = """
            SELECT d.id, d.doctor, s.spec, d.numb
            FROM doctors AS d
            JOIN lpu AS l ON l.lpu_id = d.lpu_id
            JOIN specs AS s ON d.spec_id = s.spec_id
            WHERE d.lpu_id = ?
            ORDER BY d.id
        """
        result = self.cursor.execute(query, (lpu,)).fetchall()

        return result

    def get_spec_list(self):
        """
        Возвращает список специальностей.
        :param lpu: Название ЛПУ
        """

        query = """
            SELECT main_spec_id, spec
            FROM main_specs
        """
        result = self.cursor.execute(query).fetchall()

        return result

    def get_prep_list(self):
        """
        Возвращет список препаратов.
        """

        query = """
            SELECT id, prep
            FROM medication
        """
        result = self.cursor.execute(query).fetchall()

        return result