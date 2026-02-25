from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext

# 🔥 НОВЫЙ ИМПОРТ
from infrastructure.database.repo.pharmacy_repo import PharmacyRepository


def build_multi_select_keyboard(options: list, selected_ids: list, prefix: str) -> InlineKeyboardMarkup:
    """
    Генерация клавиатуры с чекбоксами. Поддерживает как ORM-объекты, так и кортежи (id, name).
    """
    builder = InlineKeyboardBuilder()
    selected_set = {str(x) for x in selected_ids}

    for item in options:
        # 1. Умная распаковка данных
        if isinstance(item, tuple) and len(item) == 2:
            # Если это кортеж из нашей функции ensure_prep_items_loaded
            opt_id, name = item
        else:
            # Если это ORM-объект напрямую из базы
            try:
                opt_id = getattr(item, "id")
                name = getattr(item, "prep", getattr(item, "name", "Unknown"))
            except AttributeError:
                print(f"⚠️ Ошибка: невозможно прочитать данные препарата: {item}")
                continue

        # 2. Статус чекбокса
        is_selected = str(opt_id) in selected_set

        icon = "✅" if is_selected else "⬜"
        text = f"{icon} {name}"

        # Защита от слишком длинных названий (Telegram ругается на кнопки > 64 символов)
        if len(text) > 35:
            text = text[:32] + "..."

        # callback: select_doc_5
        callback_data = f"select_{prefix}_{opt_id}"

        builder.button(text=text, callback_data=callback_data)

    builder.adjust(1)

    # 3. Нижняя панель управления
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
        pharmacy_repo: PharmacyRepository,  # <-- Перешли на репозиторий
        state: FSMContext,
        prefix: str
) -> InlineKeyboardMarkup:
    """
    Асинхронный загрузчик списка препаратов.
    """
    # 1. Получаем список из БД через новый метод
    items = await pharmacy_repo.get_preps()

    # 2. Сохраняем контекст в нативный FSM
    await state.update_data(prefix=prefix)

    # 3. Получаем уже выбранные элементы
    data = await state.get_data()
    selected = data.get("selected_items", [])

    return build_multi_select_keyboard(items, selected, prefix)