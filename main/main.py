import asyncio

from aiogram import Bot, Dispatcher

from loader import bot, dp
from handlers.menu import register, main_menu
from handlers.add import add, select_handlers, term_and_comms
from handlers.report import report
from handlers.callbacks import general_callbacks
from middlewares.error_handler import setup_error_handler


def register_routers(dispatcher: Dispatcher):
    dispatcher.include_router(register.router)
    dispatcher.include_router(main_menu.router)
    dispatcher.include_router(add.router)
    dispatcher.include_router(select_handlers.router)
    dispatcher.include_router(term_and_comms.router)
    dispatcher.include_router(report.router)
    dispatcher.include_router(general_callbacks.router)


async def main():
    # Мидлвары
    setup_error_handler(dp)

    # Роутеры
    register_routers(dp)

    # Старт
    try:
        await dp.start_polling(bot)
    finally:
        # Корректное завершение
        await bot.session.close()
        await dp.storage.close()


if __name__ == "__main__":
    asyncio.run(main())