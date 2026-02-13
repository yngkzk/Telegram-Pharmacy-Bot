import asyncio
from sqlalchemy import select
from infrastructure.database.db_helper import db_helper
from infrastructure.database.models.users import User
from infrastructure.database.models.pharmacy import Doctor

async def main():
    print("🚀 Запуск диагностики баз данных...")

    # 1. Проверяем Пользователей (Accountant.db)
    print("\n👤 --- Пользователи (из accountant.db) ---")
    async for session in db_helper.get_user_session():
        try:
            stmt = select(User).limit(3)
            result = await session.execute(stmt)
            users = result.scalars().all()
            for u in users:
                print(f"ID: {u.user_id} | Name: {u.user_name} | Approved: {u.is_approved}")
        except Exception as e:
            print(f"❌ Ошибка users: {e}")

    # 2. Проверяем Врачей (Pharmacy.db)
    print("\n👨‍⚕️ --- Врачи (из pharmacy.db) ---")
    async for session in db_helper.get_pharmacy_session():
        try:
            stmt = select(Doctor).limit(3)
            result = await session.execute(stmt)
            doctors = result.scalars().all()
            for d in doctors:
                print(f"Doc: {d.doctor} | Tel: {d.numb}")
        except Exception as e:
            print(f"❌ Ошибка doctors: {e}")

if __name__ == "__main__":
    asyncio.run(main())