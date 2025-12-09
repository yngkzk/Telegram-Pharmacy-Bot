from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from storage.temp_data import TempDataManager
from keyboard.inline.menu_kb import get_main_menu_inline

# We import reportsDB to save data, and pharmacyDB for backup data fetching
from loader import pharmacyDB, reportsDB
from utils.logger.logger_config import logger
from states.add.prescription_state import PrescriptionFSM

router = Router()


# ============================================================
# 🛠 HELPER: RECONSTRUCT DATA
# ============================================================
async def _get_report_data(state: FSMContext):
    """
    Helper to fetch and format all report data for display/saving.
    """
    data = await TempDataManager.get_all(state)
    prefix = data.get("prefix", "doc")

    # 1. Rebuild Drug Names (Safety check if prep_map was cleared)
    # This is primarily for the Doctor flow or fallback
    selected_ids = data.get("selected_items", [])
    prep_map = data.get("prep_map")  # Ensure this key matches select_handlers

    if not prep_map and selected_ids:
        # If map is missing, quick fetch from DB to rebuild it
        try:
            rows = await pharmacyDB.get_prep_list()
            prep_map = {row["id"]: row["prep"] for row in rows}
            # Update state with restored map to avoid fetching again
            await TempDataManager.set(state, "prep_map", prep_map)
        except Exception as e:
            logger.error(f"Failed to rebuild prep_map: {e}")
            prep_map = {}

    # For Doctor Flow: List of strings
    selected_names_list = [prep_map.get(i, f"ID#{i}") for i in selected_ids] if prep_map else []

    return data, prefix, prep_map, selected_names_list


# ============================================================
# 📄 SHOW CARD (PREVIEW)
# ============================================================
@router.callback_query(F.data == "show_card", PrescriptionFSM.confirmation)
async def show_card(callback: CallbackQuery, state: FSMContext):
    # Use the helper to get normalized data (names map, prefix, etc.)
    data, prefix, prep_map, selected_names_list = await _get_report_data(state)

    # 1. TRY TO GET QUANTITIES (Pharmacy Flow)
    quantities = data.get("final_quantities", {})

    # 2. GENERATE TEXT
    if quantities:
        # SCENARIO A: We have quantities (Pharmacy)
        lines = []
        for med_id, count in quantities.items():
            name = prep_map.get(med_id) or prep_map.get(str(med_id)) or f"ID {med_id}"
            lines.append(f"▫️ {name} — <b>{count} шт.</b>")
        selected_text = "\n".join(lines)

    elif selected_names_list:
        # SCENARIO B: We have a simple list (Doctor)
        # The helper function _get_report_data already converted IDs to Names for us
        lines = [f"▫️ {name}" for name in selected_names_list]
        selected_text = "\n".join(lines)

    else:
        # SCENARIO C: Empty
        selected_text = "Список пуст"

    # 3. BUILD THE REPORT TEXT
    text = f"📋 <b>ПРЕДВАРИТЕЛЬНЫЙ ПРОСМОТР</b>\n"
    text += f"➖➖➖➖➖➖➖➖➖➖\n"

    # --- LOGIC BRANCHING ---
    if prefix == "doc":
        text += (
            f"📍 <b>ЛПУ:</b> {data.get('lpu_name')}\n"
            f"👨‍⚕️ <b>Врач:</b> {data.get('doc_name')}\n"
            f"🩺 <b>Спец:</b> {data.get('doc_spec') or 'Нет'}\n"
        )
        if data.get('term'):
            text += f"📝 <b>Условия:</b> {data.get('term')}\n"

    elif prefix == "apt":
        text += f"🏥 <b>Аптека:</b> {data.get('lpu_name')}\n"
        if data.get('quantity'):
            text += f"🔢 <b>Заявка:</b> {data.get('quantity')} уп.\n"
        if data.get('remaining'):
            text += f"📦 <b>Остаток:</b> {data.get('remaining')} уп.\n"

    # Common Footer
    comms = data.get('comms')
    if not comms:
        comms = "Без комментария"

    text += (
        f"➖➖➖➖➖➖➖➖➖➖\n"
        f"💊 <b>Препараты:</b>\n{selected_text}\n\n"
        f"💬 <b>Комментарий:</b> {comms}"
    )

    await callback.message.answer(text)
    await callback.answer()


# ============================================================
# 💾 UPLOAD REPORT (SAVE TO DB)
# ============================================================
@router.callback_query(F.data == "confirm_yes", PrescriptionFSM.confirmation)
@router.callback_query(F.data == "mp_up", PrescriptionFSM.confirmation)
async def upload_report(callback: CallbackQuery, state: FSMContext):
    # 1. Get Data
    # prep_map is returned by helper ensuring we have names
    data, prefix, prep_map, selected_names_list = await _get_report_data(state)

    user_name = callback.from_user.full_name

    # ---------------------------------------------------------
    # 🛠 FIX: CONVERT IDs TO NAMES
    # ---------------------------------------------------------
    dist_id = data.get("district")
    road = data.get("road")

    # Fetch names from DB (Handle cases where they might be None)
    if dist_id:
        district = await pharmacyDB.get_district_name(dist_id)
    else:
        district = "Unknown"

    logger.info(f"Saving report for {user_name} (Type: {prefix})")

    comment = data.get("comms", "-")

    logger.info(f"Saving report for {user_name} (Type: {prefix})")

    try:
        # =====================================================
        # 💊 PHARMACY FLOW (APOTHECARY)
        # =====================================================
        if prefix == "apt":
            lpu_name = data.get("lpu_name")

            # A. Save Main Header (Using NEW method)
            report_id = await reportsDB.save_apothecary_report(
                user=user_name,
                district=district,
                road=road,
                lpu=lpu_name,
                comment=comment
            )

            # B. Prepare Details
            # Convert {ID: Qty} -> [("Name", "Qty"), ...]
            quantities = data.get("final_quantities", {})
            items_to_save = []

            for med_id, count in quantities.items():
                # Resolve Name
                med_name = prep_map.get(med_id) or prep_map.get(str(med_id)) or f"ID {med_id}"
                items_to_save.append((med_name, count))

            # C. Save Details (Using NEW method)
            await reportsDB.save_apothecary_preps(report_id, items_to_save)

            await callback.message.edit_text(f"✅ <b>Отчёт по аптеке «{lpu_name}» сохранён!</b>")

        # =====================================================
        # 👨‍⚕️ DOCTOR FLOW
        # =====================================================
        elif prefix == "doc":
            # A. Save Main Header (Using EXISTING method)
            report_id = await reportsDB.save_main_report(
                user=user_name,
                district=district,
                road=road,
                lpu=data.get("lpu_name"),
                doctor_name=data.get("doc_name"),
                doctor_spec=data.get("doc_spec"),
                doctor_number=data.get("doc_num", "Unknown"),
                term=data.get("term"),
                comment=comment
            )

            # B. Save Details (List of strings)
            # The helper already prepared 'selected_names_list' for us
            await reportsDB.save_preps(report_id, selected_names_list)

            await callback.message.edit_text("✅ <b>Отчёт по врачу сохранён!</b>")

        # ... Finish ...
        await callback.message.answer("Что делаем дальше?", reply_markup=get_main_menu_inline())
        await state.clear()

    except Exception as e:
        logger.critical(f"Error saving report: {e}")
        await callback.message.answer(f"❌ Ошибка: {e}")
        await callback.answer()