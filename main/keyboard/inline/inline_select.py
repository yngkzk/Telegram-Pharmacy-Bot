from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from loader import pharmacyDB
from storage.temp_data import TempDataManager


def build_multi_select_keyboard(options, selected_ids, prefix):
    """
    Генерация inline-клавиатуры с множественным выбором.
    options: список кортежей (id, name)
    selected_ids: список выбранных id
    """
    # Тут надо сохранить блок, где я буду сохранять prefix в TempDataManager

    keyboard = []

    for opt_id, name in options:
        is_selected = opt_id in selected_ids
        text = f"{'✅' if is_selected else '⬜'} {name}"
        callback_data = f"select_{prefix}_{opt_id}"

        keyboard.append([InlineKeyboardButton(text=text, callback_data=callback_data)])

    # нижние кнопки
    keyboard.append([
        InlineKeyboardButton(text="🔄 Сбросить", callback_data="reset_selection"),
        InlineKeyboardButton(text="✔ Подтвердить", callback_data="confirm_selection")
    ])

    return InlineKeyboardMarkup(inline_keyboard=keyboard)


async def get_prep_inline(state, prefix):
    """
    Асинхронный генератор клавиатуры выбора препаратов.
    ВАЖНО: теперь список препаратов получаем через await!
    """
    items = await pharmacyDB.get_prep_list()

    selected = await TempDataManager.get(state, "selected_items", [])

    return build_multi_select_keyboard(items, selected, prefix)
