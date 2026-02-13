# infrastructure/database/db_helper.py
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from utils.config.config import config

class DatabaseHelper:
    def __init__(self):
        # 1. Движок для Пользователей (Accountant)
        self.engine_users = create_async_engine(config.url_accountant, echo=False)
        self.session_users = async_sessionmaker(self.engine_users, expire_on_commit=False)

        # 2. Движок для Аптеки (Pharmacy - Основной)
        self.engine_pharmacy = create_async_engine(config.url_pharmacy, echo=False)
        self.session_pharmacy = async_sessionmaker(self.engine_pharmacy, expire_on_commit=False)

        # 3. Движок для Отчетов (Reports)
        self.engine_reports = create_async_engine(config.url_reports, echo=False)
        self.session_reports = async_sessionmaker(self.engine_reports, expire_on_commit=False)

    # Dependency Injection методы:

    async def get_user_session(self):
        """Использовать для авторизации и профиля"""
        async with self.session_users() as session:
            yield session

    async def get_pharmacy_session(self):
        """Использовать для врачей, лпу, лекарств"""
        async with self.session_pharmacy() as session:
            yield session

    async def get_report_session(self):
        """Использовать для записи отчетов"""
        async with self.session_reports() as session:
            yield session

db_helper = DatabaseHelper()