# utils/ui_helpers.py
from aiogram import types
from aiogram.types import ReplyKeyboardRemove


async def send_inline_menu(message: types.Message, text: str, markup):
    """
    Универсальная функция:
    1. Убирает reply-клавиатуру (если есть)
    2. Отправляет inline-меню
    """
    # Убираем клавиатуру, если открыта
    await message.answer("...", reply_markup=ReplyKeyboardRemove())
    # Удаляем этот промежуточный месседж, чтобы не было "..."
    await message.bot.delete_message(message.chat.id, message.message_id + 1)

    # Отправляем основное сообщение с inline клавиатурой
    return await message.answer(text, reply_markup=markup)