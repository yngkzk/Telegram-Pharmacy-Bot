import asyncio
from contextlib import suppress
from aiogram import types
from aiogram.types import ReplyKeyboardRemove
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext


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


async def safe_clear_state(state: FSMContext):
    """
    Стирает временные данные FSM (отчеты, добавление),
    но сохраняет авторизационную сессию пользователя (регион, логин).
    """
    data = await state.get_data()

    # 1. Спасаем важные данные из-под завалов
    user_region = data.get("user_region")
    username = data.get("username")

    # 2. Сбрасываем ядерную бомбу (очищаем всё)
    await state.clear()

    # 3. Возвращаем спасенные данные обратно в чистый стейт
    session_data = {}
    if user_region:
        session_data["user_region"] = user_region
    if username:
        session_data["username"] = username

    if session_data:
        await state.update_data(**session_data)