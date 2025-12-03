from contextlib import suppress
from typing import List, Tuple, Dict

from aiogram import Router, types, F
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext

from storage.temp_data import TempDataManager
from keyboard.inline.inline_select import build_multi_select_keyboard
from loader import pharmacyDB
from utils.logger.logger_config import logger
from states.add.prescription_state import PrescriptionFSM

router = Router()


# ============================================================
# 📥 LOAD & CACHE DATA
# ============================================================
async def load_items(state: FSMContext) -> List[Tuple[int, str]]:
    """
    Loads preparations list into FSM.
    Optimized: Builds the name map immediately to save processing later.
    """
    # 1. Try to get from cache
    items = await TempDataManager.get(state, "prep_items")

    if items is None:
        # 2. Fetch from DB
        raw_rows = await pharmacyDB.get_prep_list()

        # 3. Serialize (Convert Row objects to simple tuples for FSM safety)
        items = [(row["id"], row["prep"]) for row in raw_rows]

        # 4. Create Map (ID -> Name) once and cache it
        prep_map = {item_id: name for item_id, name in items}

        await TempDataManager.set(state, "prep_items", items)
        await TempDataManager.set(state, "prep_map", prep_map)

    return items


# ============================================================
# ☑️ TOGGLE SELECTION (Check/Uncheck)
# ============================================================
@router.callback_query(F.data.startswith("select_"), PrescriptionFSM.choose_meds)
async def toggle_selection(callback: types.CallbackQuery, state: FSMContext):
    # Parse data: "select_doc_5" -> prefix="doc", option_id=5
    try:
        _, prefix, option_id = callback.data.split("_")
        option_id = int(option_id)
    except ValueError:
        await callback.answer("❌ Ошибка данных кнопки")
        return

    # Load data
    items = await load_items(state)
    selected = await TempDataManager.get(state, "selected_items", [])

    # Toggle Logic
    if option_id in selected:
        selected.remove(option_id)  # Uncheck
    else:
        selected.append(option_id)  # Check

    # Save back to FSM
    await TempDataManager.set(state, "selected_items", selected)

    # Rebuild Keyboard
    new_keyboard = build_multi_select_keyboard(items, selected, prefix)

    # Update Message (Ignore "Not Modified" errors)
    with suppress(TelegramBadRequest):
        await callback.message.edit_reply_markup(reply_markup=new_keyboard)

    await callback.answer()


# ============================================================
# 🔄 RESET SELECTION
# ============================================================
@router.callback_query(F.data == "reset_selection", PrescriptionFSM.choose_meds)
async def reset_selection(callback: types.CallbackQuery, state: FSMContext):
    items = await load_items(state)
    prefix = await TempDataManager.get(state, "prefix", "doc")  # Default fallback

    # Clear selection
    await TempDataManager.set(state, "selected_items", [])

    # Reset Keyboard
    new_keyboard = build_multi_select_keyboard(items, [], prefix)

    with suppress(TelegramBadRequest):
        await callback.message.edit_reply_markup(reply_markup=new_keyboard)

    await callback.answer("🗑 Выбор сброшен")


# ============================================================
# ✅ CONFIRM SELECTION
# ============================================================
@router.callback_query(F.data == "confirm_selection", PrescriptionFSM.choose_meds)
async def confirm_selection(callback: types.CallbackQuery, state: FSMContext):
    # 1. Load Data
    selected_ids = await TempDataManager.get(state, "selected_items", [])

    # Ensure map exists (reload if necessary)
    await load_items(state)
    prep_map = await TempDataManager.get(state, "prep_map", {})

    # 2. Validation
    if not selected_ids:
        await callback.answer("⚠️ Вы ничего не выбрали!", show_alert=True)
        return

    # 3. Prepare Names for Display
    selected_names = [prep_map.get(i, f"Unknown ID {i}") for i in selected_ids]
    formatted_list = "\n".join(f"• {name}" for name in selected_names)

    # 4. Routing Logic (Where do we go next?)
    prefix = await TempDataManager.get(state, "prefix")

    logger.info(f"User {callback.from_user.id} confirmed selection: {selected_ids} (Flow: {prefix})")

    response_text = f"✅ <b>Список сохранён:</b>\n{formatted_list}\n\n"

    if prefix == "doc":
        # DOCTOR FLOW
        response_text += "✍️ <b>Введите условия договора</b> (например: 10% скидка):"
        await state.set_state(PrescriptionFSM.contract_terms)

    elif prefix == "apt":
        # PHARMACY FLOW
        response_text += "🔢 <b>Введите количество упаковок</b> (целое число):"
        # FIXED: Now specifically setting the state for quantity
        await state.set_state(PrescriptionFSM.waiting_for_quantity)

    else:
        # Fallback for error safety
        await callback.answer("⚠️ Ошибка состояния (неизвестный тип)", show_alert=True)
        return

    # 5. UI Update
    # Replace the huge button list with the summary text
    await callback.message.edit_text(response_text)

    # 6. Clean up HEAVY temp data (Keep 'selected_items' as we need them for the final report!)
    # We remove 'prep_items' and 'prep_map' to free up memory in Redis/RAM
    await TempDataManager.remove(state, "prep_items", "prep_map")