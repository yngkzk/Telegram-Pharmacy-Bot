from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder


def get_admin_menu() -> InlineKeyboardMarkup:
    """Главное меню администратора"""
    builder = InlineKeyboardBuilder()

    builder.button(text="📥 Скачать Excel (Отчеты)", callback_data="admin_export_start")
    builder.button(text="👥 Список пользователей", callback_data="admin_users_list")
    builder.button(text="✍️ Создать задачу сотрудникам", callback_data="admin_create_task")
    builder.button(text="🔙 Назад в меню", callback_data="back_to_main")

    builder.adjust(1)

    return builder.as_markup()


def get_report_period_kb() -> InlineKeyboardMarkup:
    """Клавиатура выбора периода для отчета"""
    builder = InlineKeyboardBuilder()

    # Кнопки периодов
    builder.button(text="📅 Сегодня", callback_data="period_today")
    builder.button(text="📅 Вчера", callback_data="period_yesterday")
    builder.button(text="📅 Текущая неделя", callback_data="period_week")
    builder.button(text="📅 Текущий месяц", callback_data="period_month")

    # 🔥 НОВАЯ КНОПКА: ЗА ВСЁ ВРЕМЯ (Слитно, чтобы не сломать split)
    builder.button(text="♾ За всё время", callback_data="period_alltime")

    # Кнопка отмены
    builder.button(text="❌ Отмена", callback_data="admin_cancel")

    # Сетка: по 2 кнопки в ряд (даты), затем 1 (все время), затем 1 (отмена)
    builder.adjust(2, 2, 1, 1)

    return builder.as_markup()


def get_report_users_kb(users_list: list) -> InlineKeyboardMarkup:
    """Клавиатура выбора сотрудника."""
    builder = InlineKeyboardBuilder()

    builder.button(text="👥 Все сотрудники", callback_data="user_filter_all")

    for user in users_list:
        builder.button(text=f"👤 {user}", callback_data=f"user_filter_{user}")

    builder.button(text="🔙 Отмена", callback_data="admin_cancel")
    builder.adjust(1)

    return builder.as_markup()