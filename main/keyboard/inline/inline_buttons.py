from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from loader import pharmacyDB
from utils.text.text_utils import shorten_name
from utils.logger.logger_config import logger
from storage.temp_data import TempDataManager


# ================================================================
# 🔥 CORE BUILDER (The "Engine")
# ================================================================
async def build_shortcut_keyboard(
        items: list,
        prefix: str,
        state: FSMContext = None,
        row_width: int = 2,
        text_field: int = 1,
        id_field: int = 0,
        add_back: bool = True,  # Default to True
        add_button: bool = False
) -> InlineKeyboardMarkup:
    """
    Generates an inline keyboard from a list of DB items.
    Auto-saves button text to TempData for retrieval later.
    """
    builder = InlineKeyboardBuilder()

    for i, item in enumerate(items, start=1):
        # 1. Normalize Item Data
        if isinstance(item, (int, str)):
            item_id = str(item)
            full_text = str(item)
            url = None
        elif isinstance(item, dict):  # For dict-like rows
            item_id = str(item.get("id") or item.get("pk") or i)
            full_text = str(item.get("name") or item.get("text") or item_id)
            url = item.get("url")
        else:  # For tuples/lists (sqlite rows)
            try:
                # Try accessing by key (aiosqlite.Row)
                item_id = str(item["id"]) if "id" in item.keys() else str(item[id_field])
                full_text = str(item["name"]) if "name" in item.keys() else str(item[text_field])
                # Check for specific fields for URL
                url = item["url"] if "url" in item.keys() else None
                if not url and "pharmacy_url" in item.keys(): url = item["pharmacy_url"]
            except (IndexError, TypeError, AttributeError):
                # Fallback for plain tuples
                item_id = str(item[id_field])
                full_text = str(item[text_field])
                url = item[2] if len(item) > 2 else None

        callback_data = f"{prefix}_{item_id}"

        # 2. Save Metadata (URL & Text)
        if state:
            if url:
                await TempDataManager.save_extra(state, callback_data, url=url)
            # Save original text (e.g., full doctor name)
            await TempDataManager.save_button(state, callback_data, full_text)

        # 3. Format Display Text
        # Shorten only if it's a doctor (long names break buttons)
        display_text = shorten_name(full_text) if prefix == "doc" else full_text

        builder.button(text=display_text, callback_data=callback_data)

    # Apply grid layout
    builder.adjust(row_width)

    # 4. Footer Buttons
    footer_row = []

    if add_button:
        # "Add New" button (e.g. Add Doctor)
        footer_row.append(InlineKeyboardButton(text="➕ Добавить", callback_data=f"add_{prefix}"))

    if add_back:
        # Universal Back Button -> Main Menu
        footer_row.append(InlineKeyboardButton(text="⬅️ В меню", callback_data="back_to_main"))

    if footer_row:
        builder.row(*footer_row)  # Add footer as a separate row

    return builder.as_markup()


# ================================================================
# === STATIC MENUS (Simple actions)
# ================================================================
def get_confirm_inline(mode=False) -> InlineKeyboardMarkup:
    """
    mode=False: Yes/No (Confirm Action)
    mode=True:  View/Upload (Confirm Report)
    """
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
    builder.button(text="📊 Продажи", callback_data="report_sales")
    builder.button(text="💰 Доходы", callback_data="report_income")
    builder.button(text="🧾 Все отчёты", callback_data="report_all")
    builder.button(text="⬅️ Назад", callback_data="back_to_main")
    builder.adjust(2, 1)
    return builder.as_markup()


# ================================================================
# === DYNAMIC DB MENUS (Async)
# ================================================================
async def get_district_inline(state, mode: str) -> InlineKeyboardMarkup:
    # mode = "district" (Doctor) or "a_district" (Pharmacy)
    items = await pharmacyDB.get_district_list()
    # Assuming DB returns [{"id": 1, "name": "Almaly"}, ...]
    return await build_shortcut_keyboard(items, state=state, prefix=mode, add_back=True)


async def get_road_inline(state, mode: str) -> InlineKeyboardMarkup:
    # mode = "road" or "a_road"
    items = await pharmacyDB.get_road_list()
    # List of simple integers/strings [1, 2, 3]
    return await build_shortcut_keyboard(items, state=state, prefix=mode, add_back=True)


async def get_lpu_inline(state, district, road) -> InlineKeyboardMarkup:
    items = await pharmacyDB.get_lpu_list(district, road)
    # Prefix "lpu" -> callback "lpu_5"
    return await build_shortcut_keyboard(items, state=state, prefix="lpu", add_back=True, add_button=True)


async def get_apothecary_inline(state, district, road) -> InlineKeyboardMarkup:
    items = await pharmacyDB.get_apothecary_list(district, road)
    # Prefix "apothecary" -> callback "apothecary_5"
    return await build_shortcut_keyboard(items, state=state, prefix="apothecary", row_width=2,
                                         add_back=True, add_button=True)


async def get_spec_inline(state=None) -> InlineKeyboardMarkup:
    # Used for adding new doctors
    items = await pharmacyDB.get_spec_list()
    return await build_shortcut_keyboard(items, state=state, prefix="main_spec",
                                         add_back=False)  # No back needed here usually


async def get_doctors_inline(state, lpu) -> InlineKeyboardMarkup:
    items = await pharmacyDB.get_doctors_list(lpu)
    return await build_shortcut_keyboard(items, state=state, prefix="doc", add_back=True, add_button=True)