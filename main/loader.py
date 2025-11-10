from aiogram import Bot, Dispatcher
from utils.config.config import BOT_TOKEN
from db.database import BotDB


bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


accountantDB = BotDB("./db/models/accountant.db")
pharmacyDB = BotDB("./db/models/pharmacy.db")