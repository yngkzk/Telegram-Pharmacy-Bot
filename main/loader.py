from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from utils.config.config import BOT_TOKEN, DB_PATH_ACCOUNTANT, DB_PATH_PHARMACY, DB_PATH_REPORTS
from db.database import BotDB
from db.reports import ReportRepository

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# Инициализация баз данных
accountantDB = BotDB(DB_PATH_ACCOUNTANT)
pharmacyDB = BotDB(DB_PATH_PHARMACY)
reportsDB = ReportRepository(DB_PATH_REPORTS)