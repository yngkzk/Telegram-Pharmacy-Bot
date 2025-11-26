from aiogram.filters import BaseFilter
from aiogram import types
from loader import accountantDB


class IsLoggedInFilter(BaseFilter):
    async def __call__(self, message: types.Message) -> bool:
        user_id = message.from_user.id

        exists = await accountantDB.user_exists(user_id)
        logged = await accountantDB.is_logged_in(user_id)

        return exists and logged
