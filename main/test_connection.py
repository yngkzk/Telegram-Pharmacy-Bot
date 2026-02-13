# test_connection.py
import asyncio
import os
from sqlalchemy import select, text
from infrastructure.database.db_helper import db_helper
from infrastructure.database.models.users import User
from utils.config.config import config


async def main():
    print(f"📂 Текущая рабочая директория (cwd): {os.getcwd()}")
    print(f"🔗 URL базы данных из конфига: {config.database_url}")

    # Прямая проверка, какие таблицы видит база
    async for session in db_helper.get_session():
        try:
            print("📡 Проверяем соединение...")
            # Запрашиваем список таблиц через сырой SQL для диагностики
            result = await session.execute(text("SELECT name FROM sqlite_master WHERE type='table';"))
            tables = result.scalars().all()
            print(f"📋 Найденные таблицы в базе: {tables}")

            if "users" in tables:
                print("✅ Таблица 'users' найдена! Пробуем делать запрос через ORM...")
                stmt = select(User).limit(5)
                res = await session.execute(stmt)
                users = res.scalars().all()
                for u in users:
                    print(u)
            else:
                print("❌ Таблица 'users' НЕ найдена. Скорее всего, подключились не к тому файлу.")

        except Exception as e:
            print(f"💥 Ошибка: {e}")


if __name__ == "__main__":
    asyncio.run(main())