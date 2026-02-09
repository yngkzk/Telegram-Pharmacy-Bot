from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext

# Импортируем класс для типа (чтобы IDE подсказывала методы)
from db.database import BotDB
from storage.temp_data import TempDataManager


def build_multi_select_keyboard(options: list, selected_ids: list, prefix: str) -> InlineKeyboardMarkup:
    """
    Генерация клавиатуры с чекбоксами.
    """
    builder = InlineKeyboardBuilder()

    # ОПТИМИЗАЦИЯ: Превращаем список ID в множество строк для мгновенного поиска
    # Это работает быстрее, чем перебирать список для каждого товара
    selected_set = {str(x) for x in selected_ids}

    for item in options:
        # 1. Безопасное извлечение ID и Имени
        try:
            # Если это aiosqlite.Row или словарь
            if hasattr(item, "keys") or isinstance(item, dict):
                opt_id = item["id"]
                # Пробуем найти имя в разных полях
                name = item.get("prep") or item.get("name") or "Unknown"
            # Если это кортеж (id, name)
            elif isinstance(item, (list, tuple)):
                opt_id = item[0]
                name = item[1]
            else:
                continue
        except (IndexError, KeyError):
            continue

        # 2. Статус чекбокса
        is_selected = str(opt_id) in selected_set

        icon = "✅" if is_selected else "⬜"
        text = f"{icon} {name}"

        # callback: select_doc_5 (где doc - это prefix)
        callback_data = f"select_{prefix}_{opt_id}"

        builder.button(text=text, callback_data=callback_data)

    # Выстраиваем список в 1 колонку
    builder.adjust(1)

    # 3. Нижняя панель управления
    # Сброс выбранного
    builder.row(
        InlineKeyboardButton(text="🔄 Сброс", callback_data="reset_selection"),
        InlineKeyboardButton(text="💾 Сохранить", callback_data="confirm_selection")
    )

    # 4. Кнопка Назад
    builder.row(
        InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_main")
    )

    return builder.as_markup()


async def get_prep_inline(
        pharmacy_db: BotDB,  # <--- ГЛАВНОЕ ИЗМЕНЕНИЕ: Принимаем базу как аргумент
        state: FSMContext,
        prefix: str
) -> InlineKeyboardMarkup:
    """
    Асинхронный загрузчик списка препаратов.
    """
    # 1. Получаем список из БД через переданный объект
    items = await pharmacy_db.get_prep_list()

    # 2. Сохраняем контекст (откуда пришли: врач 'doc' или аптека 'apt')
    await TempDataManager.set(state, key="prefix", value=prefix)

    # 3. Получаем уже выбранные элементы (если есть)
    selected = await TempDataManager.get(state, "selected_items", [])

    return build_multi_select_keyboard(items, selected, prefix)