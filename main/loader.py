from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage
from utils.config.settings import config

# Инициализация бота с использованием конфига
bot = Bot(
    token=config.bot_token.get_secret_value(),
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)

# Хранилище состояний (пока MemoryStorage, для резюме потом можно заменить на Redis)
dp = Dispatcher(storage=MemoryStorage())