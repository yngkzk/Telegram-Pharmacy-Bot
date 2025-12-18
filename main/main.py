import asyncio

from loader import bot, dp, init_databases, accountantDB, pharmacyDB, reportsDB

from handlers.menu import register, main_menu
from handlers.add import add, select_handlers, term_and_comms
from handlers.callbacks import general_callbacks
from handlers.report import report
from handlers.admin import admin_handlers
from handlers.tasks import tasks
from middlewares.error_handler import setup_error_handler


def register_routers():
    dp.include_router(register.router)
    dp.include_router(main_menu.router)
    dp.include_router(add.router)
    dp.include_router(select_handlers.router)
    dp.include_router(term_and_comms.router)
    dp.include_router(report.router)
    dp.include_router(general_callbacks.router)
    dp.include_router(tasks.router)
    dp.include_router(admin_handlers.router)


async def main():
    # --- Подключаем базы ---
    await init_databases()

    # --- Middleware ---
    setup_error_handler(dp)

    # --- Роутеры ---
    register_routers()

    # --- Запуск бота ---
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()

        # Закрытие БД
        await accountantDB.close()
        await pharmacyDB.close()
        await reportsDB.close()


if __name__ == "__main__":
    asyncio.run(main())