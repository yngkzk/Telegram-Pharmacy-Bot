from aiogram.filters import BaseFilter
from aiogram import types
from loader import accountantDB  # где хранятся пользователи


class IsLoggedInFilter(BaseFilter):
    async def __call__(self, message: types.Message) -> bool:
        user_id = message.from_user.id
        return accountantDB.user_exists(user_id) and accountantDB.is_logged_in(user_id)