import asyncio

from aiogram import types, F
from aiogram.filters import Command

from loader import accountantDB, dp, bot

from handlers.menu import register, main_menu
from handlers.add import add, select_handlers, tota_and_comms

from handlers.callbacks import general_callbacks

from middlewares.error_handler import setup_error_handler


async def main(): # Запускаем бота асинхронно
    dp.include_router(register.router)
    dp.include_router(main_menu.router)
    dp.include_router(add.router)
    dp.include_router(general_callbacks.router)
    dp.include_router(select_handlers.router)
    dp.include_router(tota_and_comms.router)
    setup_error_handler(dp)

    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())