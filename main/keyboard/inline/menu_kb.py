from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from loader import reportsDB  # ⚠️ Убедитесь, что reportsDB импортирован


async def get_main_menu_inline(user_id: int) -> InlineKeyboardMarkup:
    """
    Menu for Logged In Users.
    Теперь функция асинхронная, так как проверяет БД на наличие задач.
    """
    builder = InlineKeyboardBuilder()

    # 1. Проверяем количество непрочитанных задач
    unread_count = 0
    try:
        # Получаем число из БД (метод, который мы добавили ранее)
        unread_count = await reportsDB.get_unread_count(user_id)
    except Exception:
        # Если вдруг ошибка БД, просто показываем 0, чтобы меню не сломалось
        unread_count = 0

    # 2. Формируем текст кнопки
    if unread_count > 0:
        tasks_text = f"🔥 Задачи ({unread_count}) !!"
    else:
        tasks_text = "📋 Задачи"

    # ==========================================
    # СБОРКА КНОПОК
    # ==========================================

    # Row 1: Основные функции
    builder.button(text="📍 Маршрут (Врачи)", callback_data="menu_route")
    builder.button(text="🏥 Аптека", callback_data="menu_pharmacy")

    # Row 2: Задачи (Динамическая кнопка)
    builder.button(text=tasks_text, callback_data="show_tasks")

    # Row 3: Второстепенные
    builder.button(text="📊 Отчёты", callback_data="report_all")
    builder.button(text="💊 Отзывы", callback_data="feedback_view")

    # Row 4: Админка
    builder.button(text="⚙️ Админка", callback_data="admin_panel")

    # Row 5: Выход
    builder.button(text="🚪 Выйти", callback_data="user_log_out")

    # Сетка: 2 кнопки, 1 (Задачи), 2 кнопки, 1 (Админка), 1 (Выход)
    builder.adjust(2, 1, 2, 1, 1)

    return builder.as_markup()


def get_guest_menu_inline() -> InlineKeyboardMarkup:
    """Menu for Guests"""
    builder = InlineKeyboardBuilder()

    # Guest only needs to Register or Login
    builder.button(text="📝 Регистрация / Вход", callback_data="start_registration")

    builder.adjust(1)
    return builder.as_markup()