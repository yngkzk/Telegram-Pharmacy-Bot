import asyncio
import sys

from loader import bot, dp
from utils.config.settings import config
from utils.logger.logger_config import logger

# Импортируем классы БД
from db.database import BotDB
from db.reports import ReportRepository

# Импортируем middleware (обработчик ошибок)
from middlewares.error_handler import setup_error_handler

# Импорт роутеров
from handlers.menu import register, main_menu
from handlers.add import add, select_handlers, term_and_comms
from handlers.callbacks import general_callbacks
from handlers.report import report
from handlers.admin import admin_handlers
from handlers.tasks import tasks


async def main():
    logger.info("🚀 Starting AnovaPharmBot...")

    # 1. Инициализация баз данных (используем пути из config)
    accountant_db = BotDB(config.db_path_accountant)
    pharmacy_db = BotDB(config.db_path_pharmacy)
    reports_db = ReportRepository(config.db_path_reports)

    # 2. Подключение к БД (параллельно)
    try:
        await asyncio.gather(
            accountant_db.connect(),
            pharmacy_db.connect(),
            reports_db.connect()
        )
    except Exception as e:
        logger.critical(f"❌ Failed to connect to databases: {e}")
        sys.exit(1)

    # 3. Внедрение зависимостей (Dependency Injection)
    # Теперь базы доступны внутри хэндлеров через middleware или state
    # Но для совместимости со старым кодом мы сделаем "грязный хак" чуть позже,
    # а пока просто зарегистрируем их в workflow_data диспетчера.
    dp.workflow_data.update({
        "accountant_db": accountant_db,
        "pharmacy_db": pharmacy_db,
        "reports_db": reports_db,
        "config": config
    })

    # 4. Регистрация Middleware
    setup_error_handler(dp)

    # 5. Регистрация роутеров
    dp.include_routers(
        register.router,
        main_menu.router,
        add.router,
        select_handlers.router,
        term_and_comms.router,
        report.router,
        tasks.router,
        admin_handlers.router,
        general_callbacks.router # Callbacks лучше ставить в конце
    )

    # 6. Запуск
    try:
        await bot.delete_webhook(drop_pending_updates=True) # Удаляем старые апдейты
        await dp.start_polling(bot)
    finally:
        logger.info("🛑 Stopping bot...")
        await bot.session.close()
        # Корректное закрытие баз
        await asyncio.gather(
            accountant_db.close(),
            pharmacy_db.close(),
            reports_db.close()
        )

if __name__ == "__main__":
    try:
        if sys.platform == "win32":
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped manually")