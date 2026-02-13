import asyncio
import sys
from pathlib import Path

from loader import bot, dp
from utils.config.settings import config
from utils.logger.logger_config import logger

# --- ИМПОРТЫ БАЗ ДАННЫХ ---
from db.database import BotDB  # Старый класс (для бухгалтерии и legacy-аптеки)

# 🔥 ВАЖНО: Импортируем НОВЫЙ репозиторий отчетов
from infrastructure.database.repo.report_repo import ReportRepository

# Импорт middleware
from middlewares.error_handler import setup_error_handler

# --- ИМПОРТ РОУТЕРОВ ---
from handlers.menu import register, main_menu
# Добавляем save_handler в импорты
from handlers.add import add, select_handlers, term_and_comms, save_handler
from handlers.callbacks import general_callbacks
from handlers.report import report
from handlers.admin import admin_handlers
from handlers.tasks import tasks


async def main():
    logger.info("🚀 Starting AnovaPharmBot...")

    # 1. Инициализация баз данных

    # Старые базы (оставляем для совместимости, если Accountant еще не переписан)
    accountant_db = BotDB(config.db_path_accountant)

    # Старая pharmacy_db (если где-то еще используется BotDB, пусть живет.
    # Но новые хендлеры используют db_helper и SQLAlchemy)
    pharmacy_db = BotDB(config.db_path_pharmacy)

    # 🔥 НОВАЯ БАЗА ОТЧЕТОВ
    # Превращаем путь из конфига в Path (так требует новый класс)
    reports_file = Path(config.db_path_reports)
    reports_db = ReportRepository(reports_file)

    # 2. Подключение к БД
    try:
        # Подключаем старые
        await accountant_db.connect()
        await pharmacy_db.connect()

        # Подключаем новую (в ней создаются таблицы, если нет)
        await reports_db.connect()

    except Exception as e:
        logger.critical(f"❌ Failed to connect to databases: {e}")
        sys.exit(1)

    # 3. Внедрение зависимостей (Dependency Injection)
    # Теперь во всех хендлерах reports_db будет ссылаться на НОВЫЙ класс
    dp.workflow_data.update({
        "accountant_db": accountant_db,
        "pharmacy_db": pharmacy_db,  # Legacy
        "reports_db": reports_db,  # New Repo
        "config": config
    })

    # 4. Регистрация Middleware
    setup_error_handler(dp)

    # 5. Регистрация роутеров
    dp.include_routers(
        register.router,
        main_menu.router,

        # Блок добавления отчета
        add.router,
        select_handlers.router,
        term_and_comms.router,

        # 🔥 ВАЖНО: save_handler регистрируем ДО general_callbacks
        save_handler.router,

        report.router,
        tasks.router,
        admin_handlers.router,

        # Callbacks (ловушки) в конце
        general_callbacks.router
    )

    # 6. Запуск
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        logger.info("✅ Bot is ready to accept messages!")
        await dp.start_polling(bot)
    finally:
        logger.info("🛑 Stopping bot...")
        await bot.session.close()

        # Закрытие соединений
        await accountant_db.close()
        await pharmacy_db.close()
        await reports_db.close()


if __name__ == "__main__":
    try:
        if sys.platform == "win32":
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped manually")