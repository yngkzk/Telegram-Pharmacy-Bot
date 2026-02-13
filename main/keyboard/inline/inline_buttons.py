from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from utils.text.text_utils import shorten_name
from storage.temp_data import TempDataManager

# Константы
PAGE_SIZE = 6  # Сделал 6, чтобы не забивать экран, но можно вернуть 10


# ================================================================
# 🔥 УНИВЕРСАЛЬНЫЙ СТРОИТЕЛЬ (Helper - Senior Version)
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
    Строит клавиатуру из списка.
    Поддерживает и Словари (dict), и Объекты SQLAlchemy (class).
    """
    builder = InlineKeyboardBuilder()

    for item in items:
        try:
            # 1. ID
            item_id = getattr(item, 'id', None)
            if item_id is None:
                # У модели Road первичный ключ road_id
                item_id = getattr(item, 'road_id', None)

            if item_id is None and isinstance(item, dict):
                item_id = item.get('id') or item.get('road_id')

            if item_id is None:
                item_id = str(item)

            # 2. TEXT (Название кнопки)
            text = None

            # --- СПЕЦИАЛЬНАЯ ПРОВЕРКА ДЛЯ МАРШРУТОВ (Road) ---
            road_num = getattr(item, 'road_num', None) or (item.get('road_num') if isinstance(item, dict) else None)
            if road_num:
                text = f"Маршрут {road_num}"
                item_id = road_num
            # -------------------------------------------------

            if not text:
                # Список полей, где может лежать имя (если это не маршрут)
                possible_keys = ['name', 'doctor', 'pharmacy_name', 'spec', 'prep', 'user_name']

                for key in possible_keys:
                    val = getattr(item, key, None)
                    if val is None and isinstance(item, dict):
                        val = item.get(key)

                    if val:
                        text = str(val)
                        break

            if not text:
                text = str(item_id)  # Если совсем ничего не нашли, показываем ID

            # 3. URL
            url = getattr(item, 'url', None) or getattr(item, 'pharmacy_url', None)
            if url is None and isinstance(item, dict):
                url = item.get('url') or item.get('pharmacy_url')

            # 4. Callback
            callback_data = f"{prefix}_{item_id}"

            # 5. Сохраняем в State
            if state:
                # Важно: сохраняем чистое имя без "Маршрут ", если нужно для поиска в БД,
                # но для отображения пользователю лучше с "Маршрут".
                # Сохраним как есть на кнопке:
                await TempDataManager.save_button(state, callback_data, text)
                if url:
                    await TempDataManager.set(state, f"url_{callback_data}", url)

            # 6. Кнопка
            display_text = shorten_name(text) if len(text) > 30 else text
            builder.button(text=display_text, callback_data=callback_data)

        except Exception as e:
            print(f"Error building button for item {item}: {e}")
            continue

    builder.adjust(row_width)

    # --- ФУТЕР ---
    footer_row = []
    if add_new_btn_callback:
        footer_row.append(InlineKeyboardButton(text="➕ Добавить", callback_data=add_new_btn_callback))
    if add_back_btn:
        footer_row.append(InlineKeyboardButton(text="⬅️ В меню", callback_data="back_to_main"))
    if footer_row:
        builder.row(*footer_row)

    return builder.as_markup()


# ================================================================
# === СТАТИЧНЫЕ МЕНЮ (Без изменений)
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
# === ДИНАМИЧЕСКИЕ МЕНЮ (PURE VIEW LAYER)
# ================================================================

# Больше нет аргумента pharmacy_db!
# Мы принимаем готовый список items.

async def get_district_inline(items: list, state: FSMContext, prefix: str = "district") -> InlineKeyboardMarkup:
    """
    prefix: "district" (Врачи) или "a_district" (Аптека)
    """
    return await build_keyboard_from_items(items, prefix=prefix, state=state, row_width=2)


async def get_road_inline(items: list, state: FSMContext, prefix: str = "road") -> InlineKeyboardMarkup:
    """
    prefix: "road" (Врачи) или "a_road" (Аптека)
    """
    return await build_keyboard_from_items(items, prefix=prefix, state=state, row_width=3)

async def get_lpu_inline(items: list, state: FSMContext) -> InlineKeyboardMarkup:
    return await build_keyboard_from_items(
        items,
        prefix="lpu",
        state=state,
        row_width=1,
        add_new_btn_callback="add_lpu"
    )


async def get_apothecary_inline(items: list, state: FSMContext) -> InlineKeyboardMarkup:
    return await build_keyboard_from_items(
        items,
        prefix="apothecary",
        state=state,
        row_width=1,
        add_new_btn_callback="add_apothecary"
    )


async def get_spec_inline(items: list, state: FSMContext = None) -> InlineKeyboardMarkup:
    return await build_keyboard_from_items(items, prefix="main_spec", state=state, row_width=2)


# 🔥 ВРАЧИ (Теперь принимает список, а не БД)
async def get_doctors_inline(
        doctors: list,
        lpu_id: int,  # Нужен для callback пагинации
        page: int = 1,
        state: FSMContext = None
) -> InlineKeyboardMarkup:
    """
    Генерирует список врачей.
    doctors: Полный список врачей (или уже обрезанный, но лучше полный для пагинации здесь)
    """

    # 1. Пагинация (на случай, если передали весь список)
    # Если список короткий, срезы сработают корректно и не вызовут ошибку
    start_index = (page - 1) * PAGE_SIZE
    end_index = start_index + PAGE_SIZE

    # Если переданный список больше чем страница, режем его.
    # Если уже обрезан, берем как есть.
    if len(doctors) > PAGE_SIZE:
        current_doctors = doctors[start_index:end_index]
        has_next = end_index < len(doctors)
    else:
        current_doctors = doctors
        has_next = False

    builder = InlineKeyboardBuilder()

    # 2. Кнопки
    for doc in current_doctors:
        # Универсальный геттер (dict или object)
        d_name = getattr(doc, 'doctor', None) or getattr(doc, 'name', None)
        if d_name is None and isinstance(doc, dict):
            d_name = doc.get('doctor') or doc.get('name')

        d_name = d_name or "Unknown"

        d_id = getattr(doc, 'id', None)
        if d_id is None and isinstance(doc, dict):
            d_id = doc.get('id')

        callback_data = f"doc_{d_id}"

        # Сохраняем для кнопки "Назад/Инфо"
        if state:
            await TempDataManager.save_button(state, callback_data, d_name)

        builder.button(text=f"👨‍⚕️ {d_name}", callback_data=callback_data)

    builder.adjust(1)

    # 3. Навигация
    nav_buttons = []
    if page > 1:
        nav_buttons.append(InlineKeyboardButton(text="⬅️", callback_data=f"docpage_{lpu_id}_{page - 1}"))

    if has_next:
        nav_buttons.append(InlineKeyboardButton(text="➡️", callback_data=f"docpage_{lpu_id}_{page + 1}"))

    if nav_buttons:
        builder.row(*nav_buttons)

    # 4. Футер
    builder.row(InlineKeyboardButton(text="➕ Добавить врача", callback_data="add_doc"))
    builder.row(InlineKeyboardButton(text="🔙 Меню", callback_data="back_to_main"))

    return builder.as_markup()