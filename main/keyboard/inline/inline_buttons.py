from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from utils.text.text_utils import shorten_name
from storage.temp_data import TempDataManager

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
    Строит клавиатуру из списка объектов или словарей.
    """
    builder = InlineKeyboardBuilder()

    for item in items:
        try:
            # 1. Пытаемся достать ID
            item_id = getattr(item, 'id', None)
            if item_id is None:
                item_id = getattr(item, 'road_id', None)  # Для Road
            if item_id is None and isinstance(item, dict):
                item_id = item.get('id') or item.get('road_id')

            if item_id is None:
                item_id = str(item)  # Фолбек

            # 2. Пытаемся достать TEXT
            text = None

            # Спец. проверка для Маршрутов (нам нужен номер, а не ID)
            road_num = getattr(item, 'road_num', None)
            if road_num is None and isinstance(item, dict):
                road_num = item.get('road_num')

            if road_num is not None:
                text = f"Маршрут {road_num}"
                item_id = road_num  # В callback пишем номер маршрута!

            # Если не маршрут, ищем стандартные имена
            if not text:
                possible_keys = ['name', 'doctor', 'pharmacy_name', 'spec', 'prep', 'user_name']
                for key in possible_keys:
                    val = getattr(item, key, None)
                    if val is None and isinstance(item, dict):
                        val = item.get(key)
                    if val:
                        text = str(val)
                        break

            if not text: text = str(item_id)

            # 3. Достаем URL (если есть)
            url = getattr(item, 'url', None) or getattr(item, 'pharmacy_url', None)
            if url is None and isinstance(item, dict):
                url = item.get('url') or item.get('pharmacy_url')

            # 4. Формируем Callback
            callback_data = f"{prefix}_{item_id}"

            # 5. Сохраняем имя кнопки в кэш (НО НЕ ВЫБОР!)
            if state:
                await TempDataManager.save_button(state, callback_data, text)
                if url:
                    await TempDataManager.set(state, f"url_{callback_data}", url)

            # 6. Добавляем кнопку
            display_text = shorten_name(text) if len(text) > 30 else text
            builder.button(text=display_text, callback_data=callback_data)

        except Exception as e:
            print(f"Error building button: {e}")
            continue

    builder.adjust(row_width)

    # --- ФУТЕР ---
    footer_rows = []

    # Кнопка добавления (если передана)
    if add_new_btn_callback:
        footer_rows.append(InlineKeyboardButton(text="➕ Добавить", callback_data=add_new_btn_callback))

    # Кнопка назад
    if add_back_btn:
        footer_rows.append(InlineKeyboardButton(text="⬅️ В меню", callback_data="back_to_main"))

    # Добавляем футер отдельными строками
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
    Специальная, жесткая версия для ЛПУ.
    Гарантирует использование lpu.id, а не road_id.
    """
    builder = InlineKeyboardBuilder()

    for lpu in items:
        # 1. Явно достаем ID и ИМЯ
        # Поддерживаем и объект класса, и словарь, и Row
        lpu_id = getattr(lpu, 'lpu_id', None)
        lpu_name = getattr(lpu, 'pharmacy_name', None) or getattr(lpu, 'name', "ЛПУ")

        # Если это словарь (на всякий случай)
        if lpu_id is None and isinstance(lpu, dict):
            lpu_id = lpu.get('id')

        # Если имя не найдено
        if lpu_name is None and isinstance(lpu, dict):
            lpu_name = lpu.get('pharmacy_name') or lpu.get('name')

        # 2. Проверка на ошибку данных
        if lpu_id is None:
            print(f"❌ ОШИБКА: У ЛПУ '{lpu_name}' нет ID! Пропускаем.")
            continue

        # 3. Формируем кнопку
        callback_data = f"lpu_{lpu_id}"

        # Сохраняем имя кнопки для заголовков
        if state:
            await TempDataManager.save_button(state, callback_data, lpu_name)

        builder.button(text=lpu_name, callback_data=callback_data)

    builder.adjust(1)

    # Кнопки внизу
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
        # Теперь у нас просто id!
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

    # 1. Логика среза (Pagination Slicing)
    start_index = (page - 1) * PAGE_SIZE
    end_index = start_index + PAGE_SIZE

    # Берем срез списка
    current_doctors = doctors[start_index:end_index]

    # Проверяем, есть ли следующая страница
    has_next = end_index < len(doctors)

    # 2. Кнопки врачей
    for doc in current_doctors:
        d_name = getattr(doc, 'doctor', None) or getattr(doc, 'name', "Врач")
        d_spec = getattr(doc, 'spec', "")

        # Красивый текст: "Иванов И.И. (Терапевт)"
        btn_text = f"{d_name} ({d_spec})" if d_spec else d_name

        # Callback = doc_ID
        callback_data = f"doc_{doc.id}"

        if state:
            await TempDataManager.save_button(state, callback_data, d_name)

        builder.button(text=btn_text, callback_data=callback_data)

    builder.adjust(1)  # Врачи в 1 столбик

    # 3. Кнопки навигации (⬅️ ➡️)
    nav_buttons = []
    if page > 1:
        nav_buttons.append(InlineKeyboardButton(text="⬅️", callback_data=f"docpage_{lpu_id}_{page - 1}"))
    if has_next:
        nav_buttons.append(InlineKeyboardButton(text="➡️", callback_data=f"docpage_{lpu_id}_{page + 1}"))

    if nav_buttons:
        builder.row(*nav_buttons)

    # 4. Кнопки действий
    # 🔥 ВАЖНО: передаем lpu_id, чтобы AddHandler знал, куда добавлять!
    builder.row(InlineKeyboardButton(text="➕ Добавить врача", callback_data=f"add_doctor_{lpu_id}"))
    builder.row(
        InlineKeyboardButton(text="🔙 Меню ЛПУ", callback_data="back_to_main"))  # Можно сделать возврат к выбору ЛПУ

    return builder.as_markup()