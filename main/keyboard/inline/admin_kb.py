from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder


def get_admin_menu():
    builder = InlineKeyboardBuilder()

    # ... your existing admin buttons ...
    builder.button(text="👥 Управление пользователями", callback_data="admin_users")

    # ✅ ADD THIS BUTTON
    builder.button(text="📊 Скачать отчёт (Excel)", callback_data="admin_export_xlsx")

    builder.adjust(1)
    return builder.as_markup()