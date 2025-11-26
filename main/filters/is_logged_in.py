from aiogram.filters import BaseFilter
from aiogram import types
from loader import accountantDB


class IsLoggedInFilter(BaseFilter):
    async def __call__(self, message: types.Message) -> bool:
        user_id = message.from_user.id

        username = await accountantDB.get_active_username(user_id)
        if not username:
            return False   # никого не выбрал, не авторизован

        # теперь проверяем авторизацию по username
        return True