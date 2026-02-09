from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

# Импортируем только класс для подсказки типов (это не создает объект, это безопасно)
from db.reports import ReportRepository


async def get_main_menu_inline(user_id: int, reports_db: ReportRepository) -> InlineKeyboardMarkup:
    """
    Menu for Logged In Users.
    Теперь требует передачу reports_db явно.
    """
    builder = InlineKeyboardBuilder()

    # 1. Проверяем количество непрочитанных задач
    unread_count = 0
    try:
        # Используем переданный аргумент reports_db
        unread_count = await reports_db.get_unread_count(user_id)
    except Exception as e:
        # Логируем ошибку, чтобы не гадать, почему счетчик 0
        print(f"Error fetching unread tasks for menu: {e}")
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

    # Сетка: 2, 1, 2, 1, 1
    builder.adjust(2, 1, 2, 1, 1)

    return builder.as_markup()


def get_guest_menu_inline() -> InlineKeyboardMarkup:
    """Menu for Guests"""
    builder = InlineKeyboardBuilder()
    builder.button(text="📝 Регистрация / Вход", callback_data="start_registration")
    builder.adjust(1)
    return builder.as_markup()