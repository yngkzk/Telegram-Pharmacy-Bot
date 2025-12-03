import sys
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from utils.logger.logger_config import logger

from utils.config.config import BOT_TOKEN, DB_PATH_ACCOUNTANT, DB_PATH_PHARMACY, DB_PATH_REPORTS
from db.database import BotDB
from db.reports import ReportRepository

# ================================
# Инициализация Telegram бота
# ================================
# Мы добавляем default=DefaultBotProperties, чтобы везде работал HTML
bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)

# FSM Storage
dp = Dispatcher(storage=MemoryStorage())

# ================================
# Инициализация объектов БД
# ================================
accountantDB = BotDB(DB_PATH_ACCOUNTANT)
pharmacyDB = BotDB(DB_PATH_PHARMACY)
reportsDB = ReportRepository(DB_PATH_REPORTS)


# ================================
# Функция подключения к БД
# ================================
async def init_databases():
    """
    Подключает все базы данных.
    Использует ваш кастомный logger для красивого вывода в консоль и файл.
    """
    databases = [
        ("AccountantDB", accountantDB),
        ("PharmacyDB", pharmacyDB),
        ("ReportsDB", reportsDB)
    ]

    for name, db in databases:
        try:
            await db.connect()
            logger.info(f"✅ {name} connected successfully.")
        except Exception as e:
            logger.critical(f"❌ Failed to connect to {name}: {e}")
            raise e