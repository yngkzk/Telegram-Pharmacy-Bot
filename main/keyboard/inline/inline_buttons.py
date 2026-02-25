from typing import Sequence, Any
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from utils.text.text_utils import shorten_name


PAGE_SIZE = 6

async def build_keyboard_from_items(
        items: Sequence[Any],
        prefix: str,
        state: FSMContext = None,
        row_width: int = 1,
        add_back_btn: bool = True,
        add_new_btn_callback: str = None
) -> InlineKeyboardMarkup:
    """
    Строит клавиатуру из списка объектов ORM (SQLAlchemy).
    """
    builder = InlineKeyboardBuilder()

    for item in items:
        try:
            # 1. Умный поиск ID
            if prefix in ["road", "a_road"]:
                item_id = getattr(item, 'road_num', None)
                text = f"Маршрут {item_id}"
            else:
                # Пытаемся найти id, если его нет — ищем специфичные (lpu_id, doc_id и т.д.)
                item_id = getattr(item, 'id', None) or \
                          getattr(item, 'lpu_id', None) or \
                          getattr(item, f"{prefix}_id", None)

                # Если ID так и не найден, пропускаем этот объект, чтобы не сломать бота
                if item_id is None:
                    print(f"⚠️ Ошибка: Не удалось найти ID для объекта {item}")
                    continue

                # Ищем стандартные имена в объектах SQLAlchemy
                text = getattr(item, 'name', None) or \
                       getattr(item, 'pharmacy_name', None) or \
                       getattr(item, 'doctor', None) or \
                       getattr(item, 'spec', None) or \
                       getattr(item, 'prep', None) or \
                       str(item_id)

            # 2. Формируем Callback
            callback_data = f"{prefix}_{item_id}"

            # 3. Добавляем кнопку
            display_text = shorten_name(text) if len(text) > 30 else text
            builder.button(text=display_text, callback_data=callback_data)

        except Exception as e:
            print(f"Error building button for item {item}: {e}")
            continue

    builder.adjust(row_width)

    # --- ФУТЕР (Кнопки управления) ---
    footer_rows = []

    if add_new_btn_callback:
        footer_rows.append(InlineKeyboardButton(text="➕ Добавить", callback_data=add_new_btn_callback))

    if add_back_btn:
        footer_rows.append(InlineKeyboardButton(text="⬅️ В меню", callback_data="back_to_main"))

    for btn in footer_rows:
        builder.row(btn)

    return builder.as_markup()


# ================================================================
# === СТАТИЧНЫЕ МЕНЮ
# ================================================================

def get_confirm_inline(mode=False) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if mode:
        builder.button(text="📖 Посмотреть", callback_data="show_card")
        builder.button(text="🚀 Загрузить", callback_data="confirm_yes")
    else:
        builder.button(text="✅ Да", callback_data="confirm_yes")
        builder.button(text="❌ Нет", callback_data="confirm_no")
    builder.adjust(2)
    return builder.as_markup()


def get_cancel_inline() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="❌ Отменить", callback_data="back_to_main")
    return builder.as_markup()


def get_reports_inline() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🧾 Все отчёты", callback_data="report_all_view")
    builder.button(text="⬅️ Назад", callback_data="back_to_main")
    return builder.as_markup()


# ================================================================
# === ДИНАМИЧЕСКИЕ МЕНЮ (VIEW LAYER)
# ================================================================

async def get_district_inline(items: Sequence[Any], state: FSMContext,
                              prefix: str = "district") -> InlineKeyboardMarkup:
    return await build_keyboard_from_items(items, prefix=prefix, state=state, row_width=2)


async def get_road_inline(items: Sequence[Any], state: FSMContext, prefix: str = "road") -> InlineKeyboardMarkup:
    return await build_keyboard_from_items(items, prefix=prefix, state=state, row_width=3)


async def get_lpu_inline(items: Sequence[Any], state: FSMContext) -> InlineKeyboardMarkup:
    """Используем Фабрику для ЛПУ, сокращая код в 3 раза"""
    return await build_keyboard_from_items(
        items=items,
        prefix="lpu",
        state=state,
        row_width=1,
        add_new_btn_callback="add_lpu"
    )


async def get_apothecary_inline(items: Sequence[Any], state: FSMContext) -> InlineKeyboardMarkup:
    return await build_keyboard_from_items(
        items=items,
        prefix="apothecary",
        state=state,
        row_width=1,
        add_new_btn_callback="add_apothecary"
    )


async def get_specs_inline(specs: Sequence[Any]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for s in specs:
        s_id = getattr(s, "id", None)
        s_name = getattr(s, "spec", None)
        if s_id is not None and s_name is not None:
            builder.button(text=s_name, callback_data=f"spec_{s_id}")
    builder.adjust(2)
    return builder.as_markup()


# 🔥 ВРАЧИ (Специфичная логика с пагинацией)
async def get_doctors_inline(
        doctors: Sequence[Any],
        lpu_id: int,
        page: int = 1,
        state: FSMContext = None
) -> InlineKeyboardMarkup:
    """Генерирует список врачей с пагинацией и умным отображением специальности."""
    builder = InlineKeyboardBuilder()

    start_index = (page - 1) * PAGE_SIZE
    end_index = start_index + PAGE_SIZE
    current_doctors = doctors[start_index:end_index]
    has_next = end_index < len(doctors)

    for doc in current_doctors:
        d_name = getattr(doc, 'doctor', "Врач")

        # Безопасная попытка вытащить специальность (если она загружена через relationship)
        specialty = getattr(doc, 'specialty', None)
        spec_name = getattr(specialty, 'spec', None) if specialty else None

        btn_text = f"{d_name} ({spec_name})" if spec_name else d_name

        # Защита от слишком длинных имен на кнопке
        display_text = shorten_name(btn_text) if len(btn_text) > 35 else btn_text
        builder.button(text=display_text, callback_data=f"doc_{doc.id}")

    builder.adjust(1)

    # Пагинация
    nav_buttons = []
    if page > 1:
        nav_buttons.append(InlineKeyboardButton(text="⬅️ Назад", callback_data=f"docpage_{lpu_id}_{page - 1}"))
    if has_next:
        nav_buttons.append(InlineKeyboardButton(text="Вперед ➡️", callback_data=f"docpage_{lpu_id}_{page + 1}"))

    if nav_buttons:
        builder.row(*nav_buttons)

    # Футер
    builder.row(InlineKeyboardButton(text="➕ Добавить врача", callback_data=f"add_doctor_{lpu_id}"))
    builder.row(InlineKeyboardButton(text="🔙 Меню ЛПУ", callback_data="back_to_main"))

    return builder.as_markup()