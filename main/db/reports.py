import sqlite3
from typing import List, Dict, Any
from datetime import datetime


class ReportRepository:
    def __init__(self, db_path):
        self.conn = sqlite3.connect(db_path)
        self.cursor = self.conn.cursor()

    # ============================================================
    # 1. СОХРАНЕНИЕ ОСНОВНОГО ОТЧЁТА
    # ============================================================
    def save_main_report(
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
        """
        Создаёт основную запись отчёта и возвращает report_id
        """

        self.cursor.execute('''
            INSERT INTO main_reports
            (date, user, district, road, lpu, doc_name, doc_spec, doc_num, term, commentary)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"), user,
            district, road, lpu,
            doctor_name, doctor_spec, doctor_number,
            term, comment
        ))

        report_id = self.cursor.lastrowid
        self.conn.commit()

        return report_id

    # ============================================================
    # 2. СОХРАНЕНИЕ СПИСКА ПРЕПАРАТОВ
    # ============================================================
    def save_preps(self, report_id: int, preps: List[str]) -> None:
        """
        Добавляет список препаратов в таблицу reports_drugs
        """

        self.cursor.executemany('''
            INSERT INTO detailed_report (report_id, prep)
            VALUES (?, ?)
        ''', [(report_id, p) for p in preps])

        self.conn.commit()

    # ============================================================
    # 3. ПОЛУЧЕНИЕ ПОЛНОГО ОТЧЁТА
    # ============================================================
    def get_full_report(self, report_id: int) -> Dict[str, Any]:
        pass
