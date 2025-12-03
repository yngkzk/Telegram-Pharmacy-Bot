import asyncio
from contextlib import suppress
from aiogram import types
from aiogram.types import ReplyKeyboardRemove
from aiogram.exceptions import TelegramBadRequest

async def send_inline_menu(message: types.Message, text: str, markup):
    """
    Безопасно убирает старую reply-клавиатуру и отправляет новое inline-меню.
    """
    # 1. Отправляем сообщение для удаления клавиатуры
    # Мы сохраняем объект msg, чтобы знать точный ID
    msg_to_delete = await message.answer("⏳ Загрузка...", reply_markup=ReplyKeyboardRemove())

    # 2. Удаляем это сообщение
    # suppress(TelegramBadRequest) предотвращает краш, если сообщение уже удалено
    with suppress(TelegramBadRequest):
        await msg_to_delete.delete()

    # 3. Отправляем целевое меню
    return await message.answer(text, reply_markup=markup)