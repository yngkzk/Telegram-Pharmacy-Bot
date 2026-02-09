from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

# Импортируем только класс для подсказки типов
from db.database import BotDB

from utils.text.text_utils import shorten_name
from storage.temp_data import TempDataManager

# Константы
PAGE_SIZE = 10


# ================================================================
# 🔥 УНИВЕРСАЛЬНЫЙ СТРОИТЕЛЬ (Helper)
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
    Строит клавиатуру из списка объектов (dict или aiosqlite.Row).
    """
    builder = InlineKeyboardBuilder()

    for item in items:
        # Пытаемся достать ID и Name универсально
        try:
            item_id = item['id']

            # Проверяем все возможные варианты ключей (для совместимости)
            if 'name' in item.keys():
                text = item['name']
            elif 'doctor' in item.keys():
                text = item['doctor']
            elif 'pharmacy_name' in item.keys():
                text = item['pharmacy_name']
            elif 'spec' in item.keys():
                text = item['spec']
            elif 'prep' in item.keys():
                text = item['prep']
            else:
                text = str(item_id)  # Fallback

            # Формируем callback
            callback_data = f"{prefix}_{item_id}"

            # 🔥 ГЛАВНОЕ ИСПРАВЛЕНИЕ: СОХРАНЯЕМ ИМЯ В STATE
            # Это нужно, чтобы TempDataManager.get_button_name не возвращал None
            if state:
                await TempDataManager.save_button(state, callback_data, text)

                # Если есть URL, сохраняем его тоже
                if 'url' in item.keys() and item['url']:
                    await TempDataManager.set(state, f"url_{callback_data}", item['url'])

        except (TypeError, IndexError, AttributeError):
            # Если это просто строка или число
            item_id = str(item)
            text = str(item)
            callback_data = f"{prefix}_{item_id}"

            # Сохраняем имя и для простых кнопок
            if state:
                await TempDataManager.save_button(state, callback_data, text)

        # Обрезаем длинные имена
        display_text = shorten_name(text) if len(text) > 30 else text

        builder.button(text=display_text, callback_data=callback_data)

    builder.adjust(row_width)

    # --- КНОПКИ УПРАВЛЕНИЯ ---
    footer_row = []

    if add_new_btn_callback:
        footer_row.append(InlineKeyboardButton(text="➕ Добавить", callback_data=add_new_btn_callback))

    if add_back_btn:
        footer_row.append(InlineKeyboardButton(text="⬅️ В меню", callback_data="back_to_main"))

    if footer_row:
        builder.row(*footer_row)

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
    builder.adjust(1)
    return builder.as_markup()


# ================================================================
# === ДИНАМИЧЕСКИЕ МЕНЮ (С запросами к БД)
# ================================================================

async def get_district_inline(pharmacy_db: BotDB, state: FSMContext, mode: str) -> InlineKeyboardMarkup:
    items = await pharmacy_db.get_district_list()
    return await build_keyboard_from_items(items, prefix=mode, state=state, row_width=2)


async def get_road_inline(pharmacy_db: BotDB, state: FSMContext, mode: str) -> InlineKeyboardMarkup:
    items = await pharmacy_db.get_road_list()
    return await build_keyboard_from_items(items, prefix=mode, state=state, row_width=3)


async def get_lpu_inline(pharmacy_db: BotDB, state: FSMContext, district, road) -> InlineKeyboardMarkup:
    items = await pharmacy_db.get_lpu_list(district, road)
    return await build_keyboard_from_items(
        items,
        prefix="lpu",
        state=state,
        row_width=1,
        add_new_btn_callback="add_lpu"
    )


async def get_apothecary_inline(pharmacy_db: BotDB, state: FSMContext, district, road) -> InlineKeyboardMarkup:
    items = await pharmacy_db.get_apothecary_list(district, road)
    return await build_keyboard_from_items(
        items,
        prefix="apothecary",
        state=state,
        row_width=1,
        add_new_btn_callback="add_apothecary"
    )


async def get_spec_inline(pharmacy_db: BotDB, state: FSMContext = None) -> InlineKeyboardMarkup:
    items = await pharmacy_db.get_spec_list()
    return await build_keyboard_from_items(items, prefix="main_spec", state=state, row_width=2)


# 🔥 ВОТ ЭТА ФУНКЦИЯ, КОТОРАЯ ПОТЕРЯЛАСЬ 🔥
async def get_doctors_inline(
        pharmacy_db: BotDB,
        state: FSMContext,
        lpu_id: int,
        page: int = 1
) -> InlineKeyboardMarkup:
    """
    Генерирует список врачей с пагинацией.
    """
    # 1. Получаем ВСЕХ врачей
    all_doctors = await pharmacy_db.get_doctors(lpu_id)

    # 2. Пагинация
    start_index = (page - 1) * PAGE_SIZE
    end_index = start_index + PAGE_SIZE
    current_doctors = all_doctors[start_index:end_index]

    builder = InlineKeyboardBuilder()

    # 3. Кнопки врачей
    for doc in current_doctors:
        # Используем .get() для безопасности
        d_name = doc.get('doctor') or doc.get('name') or "Unknown"
        d_id = doc['id']

        # Формируем callback
        callback_data = f"doc_{d_id}"

        # СОХРАНЯЕМ ИМЯ В STATE (чтобы потом показать в отчете)
        if state:
            await TempDataManager.save_button(state, callback_data, d_name)

        builder.button(text=f"👨‍⚕️ {d_name}", callback_data=callback_data)

    builder.adjust(1)

    # 4. Навигация
    nav_buttons = []
    if page > 1:
        nav_buttons.append(InlineKeyboardButton(text="⬅️", callback_data=f"docpage_{lpu_id}_{page - 1}"))
    if end_index < len(all_doctors):
        nav_buttons.append(InlineKeyboardButton(text="➡️", callback_data=f"docpage_{lpu_id}_{page + 1}"))

    if nav_buttons:
        builder.row(*nav_buttons)

    # 5. Футер
    builder.row(InlineKeyboardButton(text="➕ Добавить врача", callback_data="add_doc"))
    builder.row(InlineKeyboardButton(text="🔙 Меню", callback_data="back_to_main"))

    return builder.as_markup()