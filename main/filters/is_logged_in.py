from typing import Union
from aiogram.filters import BaseFilter
from aiogram.types import Message, CallbackQuery
from loader import accountantDB

class IsLoggedInFilter(BaseFilter):
    """
    Фильтр проверяет, авторизован ли пользователь в системе.
    Работает и для Сообщений, и для CallbackQuery (кнопок).
    """
    async def __call__(self, event: Union[Message, CallbackQuery]) -> bool:
        # 1. Безопасное получение пользователя (работает и для msg, и для call)
        user = event.from_user
        if not user:
            return False

        # 2. Проверяем статус в БД
        # Метод get_active_username уже содержит проверку "WHERE logged_in = 1"
        active_username = await accountantDB.get_active_username(user.id)

        # 3. Возвращаем True, если имя найдено (значит юзер залогинен)
        return active_username is not None