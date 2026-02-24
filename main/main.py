import asyncio
import sys

from loader import bot, dp
from utils.config.config import config
from utils.logger.logger_config import logger

# Импорт middleware
from middlewares.error_handler import setup_error_handler
from middlewares.database import DatabaseMiddleware

# --- ИМПОРТ РОУТЕРОВ ---
from handlers.menu import register, main_menu
from handlers.add import add, select_handlers, term_and_comms, save_handler
from handlers.admin import admin_handlers
from handlers.tasks import tasks
from handlers.callbacks import geo_callbacks, main_menu_callbacks, med_objects_callbacks, shared_callbacks

from infrastructure.database.db_helper import db_helper


async def main():
    logger.info("🚀 Starting AnovaPharmBot...")

    # 🔥 СОЗДАЕМ ТАБЛИЦЫ ПЕРЕД ЗАПУСКОМ РОУТЕРОВ
    logger.info("🛠 Initializing databases...")
    await db_helper.init_db()

    dp.workflow_data.update({
        "config": config
    })

    # 2. Регистрация Middleware
    setup_error_handler(dp)
    dp.update.middleware(DatabaseMiddleware())

    # 3. Регистрация роутеров
    dp.include_routers(
        register.router,
        main_menu.router,

        # Блок добавления отчета
        add.router,
        select_handlers.router,
        term_and_comms.router,
        save_handler.router,

        # Остальные модули
        tasks.router,
        admin_handlers.router,

        # Callbacks (ловушки) всегда в конце
        main_menu_callbacks.router,
        geo_callbacks.router,
        med_objects_callbacks.router,
        shared_callbacks.router
    )

    # 4. Запуск
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        logger.info("✅ Bot is ready to accept messages!")
        await dp.start_polling(bot)
    finally:
        logger.info("🛑 Stopping bot...")
        await bot.session.close()


if __name__ == "__main__":
    try:
        if sys.platform == "win32":
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped manually")