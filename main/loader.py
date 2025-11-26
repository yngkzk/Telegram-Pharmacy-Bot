from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from utils.config.config import BOT_TOKEN, DB_PATH_ACCOUNTANT, DB_PATH_PHARMACY, DB_PATH_REPORTS
from db.database import BotDB
from db.reports import ReportRepository


# ================================
# Инициализация Telegram бота
# ================================
bot = Bot(token=BOT_TOKEN)

# FSM Storage
dp = Dispatcher(storage=MemoryStorage())


# ================================
# Инициализация Баз Данных
# (пока без подключения)
# ================================
accountantDB = BotDB(DB_PATH_ACCOUNTANT)
pharmacyDB = BotDB(DB_PATH_PHARMACY)
reportsDB = ReportRepository(DB_PATH_REPORTS)  # Оставляем как есть, если он синхронный


# ================================
# Функция для асинхронного подключения БД
# ================================
async def init_databases():
    """Подключает асинхронные базы данных перед стартом бота."""
    await accountantDB.connect()
    await pharmacyDB.connect()
    await reportsDB.connect()

