from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder


def get_admin_menu() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()

    # --- Старые кнопки (Пример) ---
    builder.button(text="📥 Скачать Excel (Отчеты)", callback_data="admin_export_xlsx")
    builder.button(text="👥 Список пользователей", callback_data="admin_users_list")

    # --- 👇 НОВАЯ КНОПКА: ЗАДАЧИ ---
    builder.button(text="✍️ Создать задачу сотрудникам", callback_data="admin_create_task")

    # --- 👇 НОВАЯ КНОПКА: НАЗАД ---
    builder.button(text="🔙 Назад в меню", callback_data="back_to_main")

    # Настройка сетки:
    # 1 кнопка (Excel)
    # 1 кнопка (Юзеры)
    # 1 кнопка (Задача)
    # 1 кнопка (Назад)
    builder.adjust(1, 1, 1, 1)

    return builder.as_markup()