from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from utils.text.text_utils import shorten_name

# Константы
PAGE_SIZE = 6


# ================================================================
# 🔥 УНИВЕРСАЛЬНЫЙ СТРОИТЕЛЬ
# ================================================================
async def build_keyboard_from_items(
        items: list,
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
            # 1. Достаем ID (для маршрутов это road_num, для остальных id)
            if prefix in ["road", "a_road"]:
                item_id = getattr(item, 'road_num')
                text = f"Маршрут {item_id}"
            else:
                item_id = getattr(item, 'id')
                # Ищем стандартные имена в объектах SQLAlchemy
                text = getattr(item, 'name', None) or \
                       getattr(item, 'pharmacy_name', None) or \
                       getattr(item, 'doctor', None) or \
                       getattr(item, 'spec', None) or \
                       getattr(item, 'prep', None) or \
                       str(item_id)

            # 2. Формируем Callback
            callback_data = f"{prefix}_{item_id}"

            # 3. Добавляем кнопку (без сохранения в TempDataManager!)
            display_text = shorten_name(text) if len(text) > 30 else text
            builder.button(text=display_text, callback_data=callback_data)

        except Exception as e:
            # В production логируем ошибку
            print(f"Error building button for item {item}: {e}")
            continue

    builder.adjust(row_width)

    # --- ФУТЕР ---
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

async def get_district_inline(items: list, state: FSMContext, prefix: str = "district") -> InlineKeyboardMarkup:
    return await build_keyboard_from_items(items, prefix=prefix, state=state, row_width=2)


async def get_road_inline(items: list, state: FSMContext, prefix: str = "road") -> InlineKeyboardMarkup:
    return await build_keyboard_from_items(items, prefix=prefix, state=state, row_width=3)


async def get_lpu_inline(items: list, state: FSMContext) -> InlineKeyboardMarkup:
    """
    Специальная, жесткая версия для ЛПУ. Работает с ORM объектами.
    """
    builder = InlineKeyboardBuilder()

    for lpu in items:
        lpu_id = getattr(lpu, 'id', None)
        lpu_name = getattr(lpu, 'pharmacy_name', "ЛПУ")

        if lpu_id is None:
            continue

        callback_data = f"lpu_{lpu_id}"
        builder.button(text=lpu_name, callback_data=callback_data)

    builder.adjust(1)
    builder.row(InlineKeyboardButton(text="➕ Добавить ЛПУ", callback_data="add_lpu"))
    builder.row(InlineKeyboardButton(text="⬅️ В меню", callback_data="back_to_main"))

    return builder.as_markup()


async def get_apothecary_inline(items: list, state: FSMContext) -> InlineKeyboardMarkup:
    return await build_keyboard_from_items(
        items,
        prefix="apothecary",
        state=state,
        row_width=1,
        add_new_btn_callback="add_apothecary"
    )


async def get_specs_inline(specs: list) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()

    for s in specs:
        s_id = getattr(s, "id", None)
        s_name = getattr(s, "spec", None)

        if s_id is None or s_name is None:
            continue

        builder.button(text=s_name, callback_data=f"spec_{s_id}")

    builder.adjust(2)
    return builder.as_markup()


# 🔥 ВРАЧИ (Специфичная логика с пагинацией)
async def get_doctors_inline(
        doctors: list,
        lpu_id: int,
        page: int = 1,
        state: FSMContext = None
) -> InlineKeyboardMarkup:
    """
    Генерирует список врачей с пагинацией.
    """
    builder = InlineKeyboardBuilder()

    start_index = (page - 1) * PAGE_SIZE
    end_index = start_index + PAGE_SIZE

    current_doctors = doctors[start_index:end_index]
    has_next = end_index < len(doctors)

    for doc in current_doctors:
        d_name = getattr(doc, 'doctor', "Врач")
        # Поскольку мы не делаем join, временно не показываем спецуху на кнопке,
        # либо берем её из relationship, если она предзагружена (doc.specialty.spec)
        btn_text = d_name
        callback_data = f"doc_{doc.id}"

        builder.button(text=btn_text, callback_data=callback_data)

    builder.adjust(1)

    nav_buttons = []
    if page > 1:
        nav_buttons.append(InlineKeyboardButton(text="⬅️", callback_data=f"docpage_{lpu_id}_{page - 1}"))
    if has_next:
        nav_buttons.append(InlineKeyboardButton(text="➡️", callback_data=f"docpage_{lpu_id}_{page + 1}"))

    if nav_buttons:
        builder.row(*nav_buttons)

    builder.row(InlineKeyboardButton(text="➕ Добавить врача", callback_data=f"add_doctor_{lpu_id}"))
    builder.row(InlineKeyboardButton(text="🔙 Меню ЛПУ", callback_data="back_to_main"))

    return builder.as_markup()