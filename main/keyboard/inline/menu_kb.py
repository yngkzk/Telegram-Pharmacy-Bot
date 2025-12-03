from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


def get_main_menu_inline() -> InlineKeyboardMarkup:
    """Menu for Logged In Users"""
    builder = InlineKeyboardBuilder()

    # Row 1: Core Features
    builder.button(text="📍 Маршрут (Врачи)", callback_data="menu_route")
    builder.button(text="🏥 Аптека", callback_data="menu_pharmacy")

    # Row 2: Secondary Features
    builder.button(text="📊 Отчёты", callback_data="report_all")
    builder.button(text="💊 Отзывы", callback_data="feedback_view")

    # Row 3: Admin / Settings
    builder.button(text="⚙️ Админка", callback_data="admin_panel")

    # Row 4: Logout
    builder.button(text="🚪 Выйти", callback_data="user_log_out")

    builder.adjust(2, 2, 1, 1)
    return builder.as_markup()


def get_guest_menu_inline() -> InlineKeyboardMarkup:
    """Menu for Guests"""
    builder = InlineKeyboardBuilder()

    # Guest only needs to Register or Login
    builder.button(text="📝 Регистрация / Вход", callback_data="start_registration")

    builder.adjust(1)
    return builder.as_markup()