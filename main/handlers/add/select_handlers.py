from contextlib import suppress
from typing import List, Tuple, Dict

from aiogram import Router, types, F
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext

from storage.temp_data import TempDataManager
from keyboard.inline.inline_select import build_multi_select_keyboard
from keyboard.inline.inline_buttons import get_doctors_inline
from loader import pharmacyDB
from utils.logger.logger_config import logger
from states.add.prescription_state import PrescriptionFSM

router = Router()


# ============================================================
# 📥 LOAD & CACHE DATA (Unchanged)
# ============================================================
async def load_items(state: FSMContext) -> List[Tuple[int, str]]:
    items = await TempDataManager.get(state, "prep_items")
    if items is None:
        raw_rows = await pharmacyDB.get_prep_list()
        items = [(row["id"], row["prep"]) for row in raw_rows]
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
# 🆕 HELPER: Ask for next quantity
# ============================================================
async def ask_next_quantity(message: types.Message, state: FSMContext):
    """
    Checks the queue and asks the user to input quantity for the next item.
    """
    queue = await TempDataManager.get(state, "quantity_queue", [])
    prep_map = await TempDataManager.get(state, "prep_map", {})
    prefix = await TempDataManager.get(state, "prefix")

    if not queue:
        # --- LOOP FINISHED ---
        # 1. Retrieve all collected data
        final_quantities = await TempDataManager.get(state, "final_quantities", {})

        # 2. Format final summary
        summary_text = "<b>✅ Все данные заполнены:</b>\n\n"
        for p_id, qty in final_quantities.items():
            name = prep_map.get(p_id, "Unknown")
            summary_text += f"• {name}: <b>{qty} шт.</b>\n"

        # 3. Cleanup Heavy Data (Now it is safe to remove map)
        await TempDataManager.remove(state, "prep_items", "quantity_queue")

        await message.answer(summary_text)

        # 4. Set the correct state based on user type
        if prefix == "doc":
            await state.set_state(PrescriptionFSM.doctor_comments)
        else:
            # Logic: Even if it's a pharmacy, we skip 'quantity'/'remaining' inputs
            # and go straight to comments as requested.
            await state.set_state(PrescriptionFSM.pharmacy_comments)

        # 5. Prompt the user immediately
        await message.answer("✍️ <b>Напишите комментарий</b> (или отправьте '-', если нет):")
        return

    # --- PROCESS NEXT ITEM ---
    current_id = queue[0]  # Peek at first item
    current_name = prep_map.get(current_id, "Unknown Drug")

    await message.answer(f"🔢 Введите количество для препарата:\n<b>👉 {current_name}</b>")
    await state.set_state(PrescriptionFSM.waiting_for_quantity)


# ============================================================
# ✅ CONFIRM SELECTION (Modified)
# ============================================================
@router.callback_query(F.data == "confirm_selection", PrescriptionFSM.choose_meds)
async def confirm_selection(callback: types.CallbackQuery, state: FSMContext):
    selected_ids = await TempDataManager.get(state, "selected_items", [])

    # Ensure map exists
    await load_items(state)
    prep_map = await TempDataManager.get(state, "prep_map", {})

    if not selected_ids:
        await callback.answer("⚠️ Вы ничего не выбрали!", show_alert=True)
        return

    prefix = await TempDataManager.get(state, "prefix")
    logger.info(f"User {callback.from_user.id} confirmed selection: {selected_ids}")

    if prefix == "doc":
        # DOCTOR FLOW (Old logic)
        selected_names = [prep_map.get(i, f"ID {i}") for i in selected_ids]
        formatted_list = "\n".join(f"• {name}" for name in selected_names)

        response_text = f"✅ <b>Список сохранён:</b>\n{formatted_list}\n\n"
        response_text += "✍️ <b>Введите условия договора</b> (например: 10% скидка):"

        await callback.message.edit_text(response_text)
        await state.set_state(PrescriptionFSM.contract_terms)

        # Cleanup immediately for Doctor flow
        await TempDataManager.remove(state, "prep_items", "prep_map")

    elif prefix == "apt":
        # PHARMACY FLOW (New Loop Logic)

        # 1. Initialize the Queue and Result Dict
        await TempDataManager.set(state, "quantity_queue", list(selected_ids))  # Copy list
        await TempDataManager.set(state, "final_quantities", {})

        await callback.message.edit_text("✅ <b>Список принят.</b>\nТеперь укажите количество для каждого препарата.")

        # 2. Trigger the first question
        # We pass callback.message so the helper can send a new message
        await ask_next_quantity(callback.message, state)

    else:
        await callback.answer("⚠️ Ошибка состояния", show_alert=True)


# ============================================================
# 🔢 HANDLE QUANTITY INPUT (New Handler)
# ============================================================
@router.message(PrescriptionFSM.waiting_for_quantity)
async def process_quantity_input(message: types.Message, state: FSMContext):
    # 1. Validate Input
    if not message.text.isdigit():
        await message.answer("⚠️ Пожалуйста, введите целое число.")
        return

    qty = int(message.text)

    # 2. Get State Data
    queue = await TempDataManager.get(state, "quantity_queue", [])
    final_quantities = await TempDataManager.get(state, "final_quantities", {})

    if not queue:
        # Should not happen ideally, but safety check
        await message.answer("Ошибка очереди. Попробуйте заново.")
        return

    # 3. Save Data for Current Item
    current_item_id = queue.pop(0)  # Remove first item
    final_quantities[current_item_id] = qty

    # 4. Update State
    await TempDataManager.set(state, "quantity_queue", queue)
    await TempDataManager.set(state, "final_quantities", final_quantities)

    # 5. Ask for NEXT item or Finish
    await ask_next_quantity(message, state)

# ============================================================
# 📄 PAGINATION HANDLER (Next/Prev Page)
# ============================================================
@router.callback_query(F.data.startswith("docpage_"))
async def paginate_doctors(callback: types.CallbackQuery, state: FSMContext):
    # Data format: docpage_{lpu_id}_{page_number}
    parts = callback.data.split("_")
    lpu_id = int(parts[1])
    page = int(parts[2])

    # Generate the new keyboard for the requested page
    keyboard = await get_doctors_inline(state, lpu_id=lpu_id, page=page)

    # Update the message
    # We use Try/Except to avoid errors if the message content is identical
    try:
        await callback.message.edit_reply_markup(reply_markup=keyboard)
    except Exception:
        await callback.answer() # Just answer if nothing changed

    await callback.answer()