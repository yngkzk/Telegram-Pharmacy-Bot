from aiogram import F
from aiogram.types import Update
from aiogram.exceptions import TelegramBadRequest

from utils.logger_config import logger


def setup_error_handler(dp):
    @dp.errors()
    async def error_handler(update: Update, exception: Exception):
        if isinstance(exception, TelegramBadRequest):
            logger.warning(f"TelegramBadRequest: {exception} | Update: {update}")
        else:
            logger.error(f"Unhandled error: {exception} | Update: {update}", exc_info=True)