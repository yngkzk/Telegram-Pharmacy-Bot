from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from loader import pharmacyDB


def build_multi_select_keyboard(options: list[tuple[int, str]], selected: list[int]) -> InlineKeyboardMarkup:
    """
    Создаёт inline-клавиатуру с множественным выбором.
    options: [(id, name), ...]
    selected: [id, id, ...]
    """
    keyboard = []

    for opt_id, name in options:
        is_selected = opt_id in selected
        prefix = "✅ " if is_selected else ""
        keyboard.append([
            InlineKeyboardButton(
                text=f"{prefix}{name}",
                callback_data=f"select_{opt_id}"  # короткий и безопасный callback
            )
        ])

    # Добавляем нижний ряд с кнопками управления
    keyboard.append([
        InlineKeyboardButton(text="🔄 Сбросить", callback_data="reset_selection"),
        InlineKeyboardButton(text="✅ Подтвердить", callback_data="confirm_selection")
    ])

    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_prep_inline() -> InlineKeyboardMarkup:
    items = pharmacyDB.get_prep_list()
    return build_multi_select_keyboard(items, [])