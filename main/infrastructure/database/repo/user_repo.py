from typing import Optional, List
from sqlalchemy import select, update, text
from sqlalchemy.ext.asyncio import AsyncSession
from infrastructure.database.models.users import User

class UserRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_user(self, user_id: int) -> Optional[User]:
        stmt = select(User).where(User.user_id == user_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_user_by_username(self, username: str) -> Optional[User]:
        """Поиск по имени (для логина)"""
        stmt = select(User).where(User.user_name == username)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_approved_usernames(self) -> List[str]:
        """Получить список имен всех подтвержденных пользователей"""
        stmt = select(User.user_name).where(User.is_approved == True)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def create_user(self, user_id: int, username: str, password_hash: str, region: str) -> User:
        """Создание нового пользователя"""
        existing_user = await self.get_user(user_id)
        if existing_user:
            return existing_user

        new_user = User(
            user_id=str(user_id),
            user_name=username,
            user_password=password_hash,
            region=region,
            is_approved=False,
            logged_in=1
        )
        self.session.add(new_user)
        await self.session.commit()
        return new_user

    async def set_logged_in(self, telegram_id: int, status: bool):
        """
        Обновляет статус авторизации пользователя (logged_in).
        """

        stmt = (
            update(User)
            .where(User.user_id == telegram_id)
            .values(logged_in=status)
        )
        await self.session.execute(stmt)
        await self.session.commit()