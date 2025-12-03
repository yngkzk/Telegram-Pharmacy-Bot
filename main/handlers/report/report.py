from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from storage.temp_data import TempDataManager
from keyboard.inline.menu_kb import get_main_menu_inline

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
    Handles both Doctor and Pharmacy modes.
    """
    data = await TempDataManager.get_all(state)
    prefix = data.get("prefix", "doc")  # Default to doc if missing

    # 1. Rebuild Drug Names (Safety check if prep_map was cleared)
    selected_ids = data.get("selected_items", [])
    prep_map = data.get("prep_map")

    if not prep_map and selected_ids:
        # If map is missing, quick fetch from DB to rebuild it
        rows = await pharmacyDB.get_prep_list()
        prep_map = {row["id"]: row["prep"] for row in rows}

    selected_names = [prep_map.get(i, f"ID#{i}") for i in selected_ids] if prep_map else []
    selected_text = "\n".join([f"• {name}" for name in selected_names]) or "Ничего не выбрано"

    return data, prefix, selected_names, selected_text


# ============================================================
# 📄 SHOW CARD (PREVIEW)
# ============================================================
@router.callback_query(F.data == "show_card", PrescriptionFSM.confirmation)
async def show_card(callback: CallbackQuery, state: FSMContext):
    data, prefix, _, selected_text = await _get_report_data(state)

    # Base Header
    text = f"📋 <b>ПРЕДВАРИТЕЛЬНЫЙ ПРОСМОТР</b>\n"
    text += f"➖➖➖➖➖➖➖➖➖➖\n"

    # --- LOGIC BRANCHING ---
    if prefix == "doc":
        text += (
            f"📍 <b>ЛПУ:</b> {data.get('lpu_name')}\n"
            f"👨‍⚕️ <b>Врач:</b> {data.get('doc_name')}\n"
            f"🩺 <b>Спец:</b> {data.get('doc_spec') or 'Нет'}\n"
            f"📝 <b>Условия:</b> {data.get('term')}\n"
        )
    elif prefix == "apt":
        text += (
            f"🏥 <b>Аптека:</b> {data.get('lpu_name')}\n"
            f"🔢 <b>Заявка:</b> {data.get('quantity')} уп.\n"
            f"📦 <b>Остаток:</b> {data.get('remaining')} уп.\n"
        )

    # Common Footer
    text += (
        f"➖➖➖➖➖➖➖➖➖➖\n"
        f"💊 <b>Препараты:</b>\n{selected_text}\n\n"
        f"💬 <b>Комментарий:</b> {data.get('comms')}"
    )

    await callback.message.answer(text)
    await callback.answer()


# ============================================================
# 💾 UPLOAD REPORT (SAVE TO DB)
# ============================================================
@router.callback_query(F.data == "confirm_yes", PrescriptionFSM.confirmation)  # Changed button ID to standard
@router.callback_query(F.data == "mp_up", PrescriptionFSM.confirmation)  # Keep old ID just in case
async def upload_report(callback: CallbackQuery, state: FSMContext):
    # 1. Get Data
    data, prefix, selected_names, _ = await _get_report_data(state)
    user_name = callback.from_user.full_name

    logger.info(f"Saving report for {user_name} (Type: {prefix})")

    try:
        # 2. Map Data to DB Schema
        # Note: Your current DB schema is built for doctors.
        # We adapt Pharmacy data to fit into existing columns to avoid DB migration.

        if prefix == "doc":
            # Direct mapping
            r_lpu = data.get('lpu_name')
            r_doc = data.get('doc_name')
            r_spec = data.get('doc_spec')
            r_num = data.get('doc_num')
            r_term = data.get('term')

        elif prefix == "apt":
            # Adaptation:
            # LPU -> Pharmacy Name
            # Doc Name -> "Аптека"
            # Term -> Quantity info
            r_lpu = data.get('lpu_name')
            r_doc = "Фармацевт / Аптека"
            r_spec = "Аптека"
            r_num = None
            # Combine Quantity/Remaining into the 'term' field
            r_term = f"Заявка: {data.get('quantity')}, Остаток: {data.get('remaining')}"

        # 3. Save Main Report
        report_id = await reportsDB.save_main_report(
            user=user_name,
            district=data.get("district", "Unknown"),
            road=data.get("road", "Unknown"),
            lpu=r_lpu,
            doctor_name=r_doc,
            doctor_spec=r_spec,
            doctor_number=r_num,
            term=r_term,
            comment=data.get("comms")
        )

        # 4. Save Drugs (Details)
        await reportsDB.save_preps(report_id, selected_names)

        # 5. Success & Exit
        await callback.message.edit_text("✅ <b>Отчет успешно загружен!</b>")

        # Return to Menu
        await callback.message.answer(
            "Что делаем дальше?",
            reply_markup=get_main_menu_inline()
        )
        await state.clear()

    except Exception as e:
        logger.critical(f"Error saving report: {e}")
        await callback.message.answer("❌ Ошибка при сохранении. Обратитесь к админу.")
        await callback.answer()

