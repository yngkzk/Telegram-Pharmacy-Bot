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
    items: list[tuple[str, str]],
    row_width: int = 2,
    add_back: bool = False
) -> InlineKeyboardMarkup:

    keyboard = []
    for i in range(0, len(items), row_width):
        keyboard.append([
            InlineKeyboardButton(text=text, callback_data=data)
            for text, data in items[i:i + row_width]
        ])

    if add_back:
        keyboard.append([InlineKeyboardButton(text="🔙 Назад", callback_data="back")])

    return InlineKeyboardMarkup(inline_keyboard=keyboard)


# ================================================================
# 🔥 УНИВЕРСАЛЬНЫЙ POST-PROCESSOR ДЛЯ ДИНАМИЧЕСКИХ СПИСКОВ
# ================================================================
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

        # ===== Определяем id, текст и URL =====
        if isinstance(item, (int, str)):
            item_id = str(item)
            full_text = str(item)
            url = None

        elif isinstance(item, dict):
            item_id = str(item.get("id") or item.get("pk") or item.get("value") or i)
            full_text = str(item.get("name") or item.get("text") or item.get("title") or item_id)
            url = item.get("url")

        else:
            item_id = str(item[id_field])
            full_text = str(item[text_field])
            url = item[2] if len(item) > 2 else None

        callback_data = f"{prefix}_{item_id}"

        # ==== Если есть URL — сохраняем в TempData ====
        if url and state:
            await TempDataManager.save_extra(state, callback_data, url=url)

        # ==== Сокращение ФИО только для врачей ====
        text = shorten_name(full_text) if prefix == "doc" else full_text

        # ==== Запоминаем оригинальный текст ====
        if state:
            await TempDataManager.save_button(state, callback_data, full_text)

        row.append(InlineKeyboardButton(text=text, callback_data=callback_data))

        if i % row_width == 0:
            rows.append(row)
            row = []

    if row:
        rows.append(row)

    # Кнопка "Добавить"
    if add_button:
        rows.append([InlineKeyboardButton(text="➕ Добавить", callback_data=f"add_{prefix}")])

    # Назад
    if add_back:
        rows.append([InlineKeyboardButton(text="🔙 Назад", callback_data="back")])

    return InlineKeyboardMarkup(inline_keyboard=rows)


# ================================================================
# === ОБЫЧНЫЕ INLINE МЕНЮ (без БД)
# ================================================================
def get_confirm_inline(mode=False) -> InlineKeyboardMarkup:
    items = [
        ("📖 Посмотреть", "show_card"),
        ("📝 Загрузить", "mp_up")
    ] if mode else [
        ("✅ Подтвердить", "confirm_yes"),
        ("❌ Отменить", "confirm_no")
    ]
    return build_inline_keyboard(items, row_width=2)


def get_cancel_inline() -> InlineKeyboardMarkup:
    return build_inline_keyboard([("🔙 Назад", "back")])


def get_users_inline() -> InlineKeyboardMarkup:
    items = [
         ("🗺 Маршрут", "user_road"),
         ("🏥 ЛПУ", "user_lpu"),
         ("📌 Аптека", "user_apothecary"),
         ("🚪 Выйти из уч. записи", "user_log_out")
    ]
    return build_inline_keyboard(items, row_width=2, add_back=True)


def get_reports_inline() -> InlineKeyboardMarkup:
    items = [
        ("📊 Продажи", "report_sales"),
        ("💰 Доходы", "report_income"),
        ("🧾 Все отчёты", "report_all")
    ]
    return build_inline_keyboard(items, row_width=2, add_back=True)


def get_feedback_inline() -> InlineKeyboardMarkup:
    items = [
        ("⭐ Оставить отзыв", "feedback_add"),
        ("📋 Посмотреть отзывы", "feedback_view")
    ]
    return build_inline_keyboard(items, row_width=1, add_back=True)


def get_admin_inline() -> InlineKeyboardMarkup:
    items = [
        ("👥 Пользователи", "admin_users"),
        ("📦 Продукты", "admin_products"),
        ("⚙️ Настройки", "admin_settings")
    ]
    return build_inline_keyboard(items, row_width=2, add_back=True)


# ================================================================
# === СПИСКИ ИЗ БАЗЫ ДАННЫХ — ВСЕ async!
# ================================================================
async def get_district_inline(state, mode: str) -> InlineKeyboardMarkup:
    items = await pharmacyDB.get_district_list()
    logger.info(f"items in get_district - {items}")
    return await build_shortcut_keyboard(items, state=state, prefix=mode, add_back=True)


async def get_road_inline(state, mode: str) -> InlineKeyboardMarkup:
    items = await pharmacyDB.get_road_list()
    logger.info(f"items in road_list - {items}")
    return await build_shortcut_keyboard(items, state=state, prefix=mode, add_back=True)


async def get_lpu_inline(state, district, road) -> InlineKeyboardMarkup:
    items = await pharmacyDB.get_lpu_list(district, road)
    logger.info(f"items in get_lpu - {items}")
    return await build_shortcut_keyboard(items, state=state, prefix="lpu", add_back=True, add_button=True)


async def get_apothecary_inline(state, district, road) -> InlineKeyboardMarkup:
    items = await pharmacyDB.get_apothecary_list(district, road)
    logger.info(f"items in get_apothecary - {items}")
    return await build_shortcut_keyboard(items, state=state, prefix="apothecary", row_width=3,
                                         add_back=True, add_button=True)


async def get_spec_inline(state) -> InlineKeyboardMarkup:
    items = await pharmacyDB.get_spec_list()
    logger.info(f"items in get_spec - {items}")
    return await build_shortcut_keyboard(items, state=state, prefix="main_spec", add_back=True)


async def get_doctors_inline(state, lpu) -> InlineKeyboardMarkup:
    items = await pharmacyDB.get_doctors_list(lpu)
    logger.info(f"items in get_doctors - {items}")
    return await build_shortcut_keyboard(items, state=state, prefix="doc", add_back=True, add_button=True)


async def get_prep_inline(state) -> InlineKeyboardMarkup:
    items = await pharmacyDB.get_prep_list()
    logger.info(f"ДБ pharmacy.db - результат {items}")
    return await build_shortcut_keyboard(items, state=state, prefix="prep", add_back=True)
