from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder


def get_admin_menu() -> InlineKeyboardMarkup:
    """Главное меню администратора"""
    builder = InlineKeyboardBuilder()

    # --- 👇 ИЗМЕНИЛИ callback_data НА admin_export_start ---
    # Это важно, чтобы запустился выбор даты, а не старый код
    builder.button(text="📥 Скачать Excel (Отчеты)", callback_data="admin_export_start")

    builder.button(text="👥 Список пользователей", callback_data="admin_users_list")
    builder.button(text="✍️ Создать задачу сотрудникам", callback_data="admin_create_task")
    builder.button(text="🔙 Назад в меню", callback_data="back_to_main")

    # Сетка: по 1 кнопке в ряд
    builder.adjust(1, 1, 1, 1)

    return builder.as_markup()


def get_report_period_kb() -> InlineKeyboardMarkup:
    """Клавиатура выбора периода для отчета"""
    builder = InlineKeyboardBuilder()

    # Кнопки периодов
    builder.button(text="📅 Сегодня", callback_data="period_today")
    builder.button(text="📅 Вчера", callback_data="period_yesterday")
    builder.button(text="📅 Текущая неделя", callback_data="period_week")
    builder.button(text="📅 Текущий месяц", callback_data="period_month")

    # Кнопка отмены
    builder.button(text="❌ Отмена", callback_data="admin_cancel")

    # Сетка: по 2 кнопки в ряд, отмена внизу
    builder.adjust(2, 2, 1)

    return builder.as_markup()


def get_report_users_kb(users_list: list) -> InlineKeyboardMarkup:
    """
    Клавиатура выбора сотрудника.
    users_list: список имен пользователей (строк).
    """
    builder = InlineKeyboardBuilder()

    # 1. Кнопка "ВСЕ" (Сначала)
    builder.button(text="👥 Все сотрудники", callback_data="user_filter_all")

    # 2. Генерируем кнопки для каждого юзера
    for user in users_list:
        # callback: user_filter_Ivan
        builder.button(text=f"👤 {user}", callback_data=f"user_filter_{user}")

    # 3. Кнопка Назад (вернет к выбору периода или в меню)
    builder.button(text="🔙 Отмена", callback_data="admin_cancel")

    # Сетка: 1 колонка
    builder.adjust(1)

    return builder.as_markup()