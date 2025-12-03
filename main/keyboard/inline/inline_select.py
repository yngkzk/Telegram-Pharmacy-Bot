from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from loader import pharmacyDB
from storage.temp_data import TempDataManager


def build_multi_select_keyboard(options: list, selected_ids: list, prefix: str) -> InlineKeyboardMarkup:
    """
    Генерация клавиатуры с чекбоксами.
    Безопасно обрабатывает и кортежи, и объекты базы данных (Row).
    """
    builder = InlineKeyboardBuilder()

    for item in options:
        # 1. Безопасное извлечение ID и Имени
        # Если это Row из БД (словарь)
        if hasattr(item, "keys") or isinstance(item, dict):
            opt_id = item["id"]
            name = item["prep"]  # Убедитесь, что в SQL запросе поле называется 'prep'
        # Если это кортеж (id, name)
        elif isinstance(item, (list, tuple)):
            opt_id = item[0]
            name = item[1]
        else:
            continue  # Пропускаем битые данные

        # 2. Статус чекбокса
        # Приводим к int, чтобы сравнение работало корректно
        # Это предотвращает баг, когда ID "5" (str) не совпадает с 5 (int)
        is_selected = int(opt_id) in [int(x) for x in selected_ids]

        text = f"✅ {name}" if is_selected else f"⬜ {name}"
        callback_data = f"select_{prefix}_{opt_id}"

        builder.button(text=text, callback_data=callback_data)

    # Выстраиваем список в 1 колонку
    builder.adjust(1)

    # 3. Нижняя панель управления (Сброс / Сохранить)
    control_buttons = [
        InlineKeyboardButton(text="🔄 Сброс", callback_data="reset_selection"),
        InlineKeyboardButton(text="💾 Сохранить", callback_data="confirm_selection")
    ]
    builder.row(*control_buttons)

    # 4. Кнопка Отмены/Назад
    # (Возвращает к выбору врача/аптеки, если передумали)
    # Используем back_to_main или generic back
    builder.row(
        InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_main")
    )

    return builder.as_markup()


async def get_prep_inline(state, prefix: str) -> InlineKeyboardMarkup:
    """
    Асинхронный загрузчик списка препаратов.
    """
    # 1. Получаем список из БД
    items = await pharmacyDB.get_prep_list()

    # 2. Сохраняем контекст (откуда пришли: врач 'doc' или аптека 'apt')
    await TempDataManager.set(state, key="prefix", value=prefix)

    # 3. Получаем уже выбранные элементы (если есть)
    selected = await TempDataManager.get(state, "selected_items", [])

    return build_multi_select_keyboard(items, selected, prefix)