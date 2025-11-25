from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters.callback_data import CallbackData

from loader import accountantDB, pharmacyDB

from utils.text.text_utils import shorten_name
from utils.logger.logger_config import logger

from storage.temp_data import TempDataManager


# === CallbackData схемы ===
class DistrictCallback(CallbackData, prefix="district"):
    id: int


class RoadCallback(CallbackData, prefix="road"):
    district: str
    num: int


class LpuCallback(CallbackData, prefix="lpu"):
    district: str
    road: int
    name: str


# === Универсальный генератор inline-клавиатур ===
def build_inline_keyboard(
    items: list[tuple[str, str]],  # (текст, callback_data)
    row_width: int = 2,
    add_back: bool = False
) -> InlineKeyboardMarkup:
    """
    Универсальный конструктор inline-клавиатуры.
    - items: список кортежей (текст, callback_data)
    - row_width: количество кнопок в строке
    - add_back: добавить кнопку "Назад"
    """
    keyboard = []
    for i in range(0, len(items), row_width):
        keyboard.append([
            InlineKeyboardButton(text=text, callback_data=data)
            for text, data in items[i:i + row_width]
        ])

    if add_back:
        keyboard.append([InlineKeyboardButton(text="🔙 Назад", callback_data="back")])

    return InlineKeyboardMarkup(inline_keyboard=keyboard)


async def build_shortcut_keyboard(
    items: list,
    prefix: str,
    state: FSMContext = None,
    row_width: int = 2,
    text_field: int = 1,
    id_field: int = 0,
    add_back: bool = None,
    add_button: bool = None
) -> InlineKeyboardMarkup:

    rows = []
    row = []

    for i, item in enumerate(items, start=1):

        # ===========================
        # 🔥 Определяем тип элемента
        # ===========================
        # 1) item = 5  → id=5, text="5"
        # 2) item = "Алматы" → id="Алматы", text="Алматы"
        # 3) item = (1,"Doc") → id=item[id_field], text=item[text_field]
        # 4) item = {"id":1,"name":"Doc"} → поддержим тоже

        if isinstance(item, (int, str)):
            item_id = str(item)
            full_text = str(item)
            url = None

        elif isinstance(item, dict):
            item_id = str(item.get("id") or item.get("pk") or item.get("value") or i)
            full_text = str(item.get("name") or item.get("text") or item.get("title") or item_id)
            url = item.get("url")

        else:
            # tuple / list
            item_id = str(item[id_field])
            full_text = str(item[text_field])
            url = item[2] if len(item) > 2 else None

        callback_data = f"{prefix}_{item_id}"

        # ===========================
        # 🔗 Если есть URL — сохраняем
        # ===========================
        if url and state:
            await TempDataManager.save_extra(state, callback_data, url=url)

        # ===========================
        # 🧠 Сокращение ФИО для врачей
        # ===========================
        text = shorten_name(full_text) if prefix == "doc" else full_text

        # ===========================
        # 🧠 Запоминаем оригинальный текст
        # ===========================
        if state:
            await TempDataManager.save_button(state, callback_data, full_text)

        # ===========================
        # 🔘 Создаём кнопку
        # ===========================
        row.append(InlineKeyboardButton(text=text, callback_data=callback_data))

        if i % row_width == 0:
            rows.append(row)
            row = []

    if row:
        rows.append(row)

    # ➕ Добавить
    if add_button:
        rows.append([InlineKeyboardButton(text="➕ Добавить", callback_data=f"add_{prefix}")])

    # 🔙 Назад
    if add_back:
        rows.append([InlineKeyboardButton(text="🔙 Назад", callback_data="back")])

    return InlineKeyboardMarkup(inline_keyboard=rows)


# === подтверждение действий ===
def get_confirm_inline(mode=False) -> InlineKeyboardMarkup:
    if mode:
        items = [
            ("📖 Посмотреть", "show_card"),
            ("📝 Загрузить", "mp_up")
        ]
    else:
        items = [
            ("✅ Подтвердить", "confirm_yes"),
            ("❌ Отменить", "confirm_no")
        ]
    return build_inline_keyboard(items, row_width=2)

def get_cancel_inline() -> InlineKeyboardMarkup:
    items = [
        ("🔙 Назад", "back")
    ]
    return build_inline_keyboard(items)


# === inline меню для пользователей ===
def get_users_inline() -> InlineKeyboardMarkup:
    items = [
         ("🗺 Маршрут", "user_road"),
         ("🏥 ЛПУ", "user_lpu"),
         ("📌 Аптека", "user_apothecary"),
         ("🚪 Выйти из уч. записи", "user_log_out")
    ]
    return build_inline_keyboard(items, row_width=2, add_back=True)


# === inline меню для отчётов ===
def get_reports_inline() -> InlineKeyboardMarkup:
    items = [
        ("📊 Продажи", "report_sales"),
        ("💰 Доходы", "report_income"),
        ("🧾 Все отчёты", "report_all")
    ]
    return build_inline_keyboard(items, row_width=2, add_back=True)


# === inline меню для отзывов ===
def get_feedback_inline() -> InlineKeyboardMarkup:
    items = [
        ("⭐ Оставить отзыв", "feedback_add"),
        ("📋 Посмотреть отзывы", "feedback_view")
    ]
    return build_inline_keyboard(items, row_width=1, add_back=True)


# === inline меню администратора ===
def get_admin_inline() -> InlineKeyboardMarkup:
    items = [
        ("👥 Пользователи", "admin_users"),
        ("📦 Продукты", "admin_products"),
        ("⚙️ Настройки", "admin_settings")
    ]
    return build_inline_keyboard(items, row_width=2, add_back=True)


# === inline список Районов ===
async def get_district_inline(state, mode: str) -> InlineKeyboardMarkup:
    items = pharmacyDB.get_district_list()
    logger.info(f"items in get_district - {items}")
    keyboard = await build_shortcut_keyboard(items=items, state=state, prefix=mode, row_width=2,
                                   add_back=True, add_button=False)
    return keyboard


# === inline список Маршрутов ===
async def get_road_inline(state, mode: str) -> InlineKeyboardMarkup:
    """Создаёт inline-клавиатуру со списком маршрутов"""
    items = pharmacyDB.get_road_list() # например, [1, 2, 3, 4, 5, 6, 7]
    logger.info(f"items in road_list - {items}")
    keyboard = await build_shortcut_keyboard(items=items, state=state, prefix=mode, row_width=2,
                                             add_back=True, add_button=False)
    return keyboard


# === inline список ЛПУ ===
async def get_lpu_inline(state, district, road) -> InlineKeyboardMarkup:
    """Создаёт inline-клавиатуру со списком ЛПУ"""
    items = pharmacyDB.get_lpu_list(district, road)
    logger.info(f"items in get_lpu - {items}")
    keyboard = await build_shortcut_keyboard(items=items, state=state, prefix="lpu", row_width=2,
                                             add_back=True, add_button=True)
    return keyboard

# === inline список Аптек ===
async def get_apothecary_inline(state, district, road) -> InlineKeyboardMarkup:
    """Создаёт inline-клавиатуру со списком аптек"""
    items = pharmacyDB.get_apothecary_list(district, road)
    logger.info(f"items in get_apothecary - {items}")
    keyboard = await build_shortcut_keyboard(items=items, state=state, prefix="apothecary", row_width=3,
                                             add_back=True, add_button=True)
    return keyboard


# === Специальность Врача ===
async def get_spec_inline(state) -> InlineKeyboardMarkup:
    """Создаёт inline-клавиатуру со списком специальностей"""
    items = pharmacyDB.get_spec_list()
    logger.info(f"items in get_spec - {items}")
    keyboard = await build_shortcut_keyboard(items=items, state=state, prefix="main_spec", row_width=2,
                                             add_back=True, add_button=False)
    return keyboard


# === inline список Врачей ===
async def get_doctors_inline(state, lpu) -> InlineKeyboardMarkup:
    """Создаёт inline-клавиатуру со списком врачей"""
    items = pharmacyDB.get_doctors_list(lpu)
    logger.info(f"LPU in get_doctors_inline - {lpu}")
    logger.info(f"items in get_doctors - {items}")
    keyboard = await build_shortcut_keyboard(items=items, state=state, prefix="doc", row_width=2,
                                             add_back=True, add_button=True)
    return keyboard


# === inline список Препаратов ===
async def get_prep_inline(state) -> InlineKeyboardMarkup:
    """Создаёт inline-клавиатуру со списком препаратов"""
    items = pharmacyDB.get_prep_list()
    logger.info(f"ДБ pharmacy.db - результат {items}")
    keyboard = await build_shortcut_keyboard(items=items, state=state, prefix="prep", row_width=2,
                                             add_back=True, add_button=False)
    return keyboard