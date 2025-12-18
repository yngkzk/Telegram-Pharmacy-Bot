from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardRemove
from aiogram.fsm.context import FSMContext

from storage.temp_data import TempDataManager
from keyboard.inline.menu_kb import get_main_menu_inline
from keyboard.inline.inline_select import get_prep_inline

from loader import pharmacyDB, reportsDB
from utils.logger.logger_config import logger
from states.add.prescription_state import PrescriptionFSM

router = Router()


# ============================================================
# 📥 ПОЛУЧЕНИЕ ДАННЫХ ИЗ STATE (Helper) + АВТО-ИСПРАВЛЕНИЕ
# ============================================================
async def _get_report_data(state: FSMContext):
    data = await TempDataManager.get_all(state)
    prefix = data.get("prefix")

    # 🛠 АВТО-ОПРЕДЕЛЕНИЕ ТИПА (Если prefix потерялся)
    if not prefix:
        # Если есть сложные количества (словарь) — это точно Аптека
        if data.get("final_quantities"):
            prefix = "apt"
        # Если есть имя врача — это точно Врач
        elif data.get("doc_name"):
            prefix = "doc"
        else:
            # На всякий случай (чтобы не падало)
            prefix = "unknown"

    # Загружаем карту препаратов (ID -> Имя)
    prep_items = data.get("prep_items", [])
    if not prep_items:
        raw_rows = await pharmacyDB.get_prep_list()
        prep_items = [(row["id"], row["prep"]) for row in raw_rows]

    prep_map = {item_id: name for item_id, name in prep_items}

    selected_ids = data.get("selected_items", [])

    selected_names_list = []
    for i in selected_ids:
        name = prep_map.get(i) or f"ID {i}"
        selected_names_list.append(name)

    return data, prefix, prep_map, selected_names_list


# ============================================================
# 📄 ПРЕДВАРИТЕЛЬНЫЙ ПРОСМОТР (SHOW CARD)
# ============================================================
@router.callback_query(F.data == "show_card", PrescriptionFSM.confirmation)
async def show_card(callback: CallbackQuery, state: FSMContext):
    data, prefix, prep_map, selected_names_list = await _get_report_data(state)
    quantities = data.get("final_quantities", {})

    selected_text = "Список пуст"

    # --- АПТЕКА ---
    if prefix == "apt" and quantities:
        lines = []
        for med_id, val in quantities.items():
            name = prep_map.get(med_id) or prep_map.get(str(med_id)) or f"ID {med_id}"

            if isinstance(val, dict):
                req = val.get('req', 0)
                rem = val.get('rem', 0)
                lines.append(f"▫️ {name} — <b>Заявка: {req} / Остаток: {rem}</b>")
            else:
                lines.append(f"▫️ {name} — <b>{val}</b>")
        selected_text = "\n".join(lines)

    # --- ВРАЧ ---
    elif prefix == "doc" and selected_names_list:
        lines = [f"▫️ {name}" for name in selected_names_list]
        selected_text = "\n".join(lines)

    # Формируем текст
    text = f"📋 <b>ПРЕДВАРИТЕЛЬНЫЙ ПРОСМОТР</b>\n"
    text += f"➖➖➖➖➖➖➖➖➖➖\n"

    lpu_name = data.get('lpu_name', 'Не указано')

    if prefix == "doc":
        doc_name = data.get('doc_name', 'Не указан')
        doc_spec = data.get('doc_spec') or 'Нет'
        text += (
            f"📍 <b>ЛПУ:</b> {lpu_name}\n"
            f"👨‍⚕️ <b>Врач:</b> {doc_name}\n"
            f"🩺 <b>Спец:</b> {doc_spec}\n"
        )
        if data.get('term'):
            text += f"📝 <b>Условия:</b> {data.get('term')}\n"

    elif prefix == "apt":
        text += f"🏥 <b>Аптека:</b> {lpu_name}\n"

    comms = data.get('comms') or "Без комментария"
    text += (
        f"➖➖➖➖➖➖➖➖➖➖\n"
        f"💊 <b>Препараты:</b>\n{selected_text}\n\n"
        f"💬 <b>Комментарий:</b> {comms}"
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Сохранить", callback_data="confirm_yes"),
            InlineKeyboardButton(text="✏️ Изменить", callback_data="back_to_meds")
        ]
    ])

    await callback.message.answer(text, reply_markup=kb)
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.answer()


# ============================================================
# 🔙 ВЕРНУТЬСЯ К ВЫБОРУ
# ============================================================
@router.callback_query(F.data == "back_to_meds")
async def back_to_med_selection(callback: CallbackQuery, state: FSMContext):
    data, prefix, _, _ = await _get_report_data(state)

    keyboard = await get_prep_inline(state, prefix=prefix)

    await state.set_state(PrescriptionFSM.choose_meds)
    await callback.message.answer("💊 <b>Выберите препараты:</b>", reply_markup=keyboard)
    await callback.message.delete()


# ============================================================
# 💾 СОХРАНЕНИЕ В БД (UPLOAD REPORT)
# ============================================================
@router.callback_query(F.data == "confirm_yes", PrescriptionFSM.confirmation)
@router.callback_query(F.data == "mp_up", PrescriptionFSM.confirmation)
async def upload_report(callback: CallbackQuery, state: FSMContext):
    # Эта функция теперь получит уже исправленный prefix
    data, prefix, prep_map, selected_names_list = await _get_report_data(state)
    user_name = callback.from_user.full_name

    district_id = data.get("district")
    road_id = data.get("road")

    try:
        district_name = await pharmacyDB.get_district_name(district_id)
    except AttributeError:
        district_name = str(district_id)

    try:
        road_name = await pharmacyDB.get_road_name(road_id)
    except AttributeError:
        road_name = str(road_id)

    logger.info(f"Saving report... User: {user_name}, Prefix: {prefix}")

    try:
        # =====================================================
        # 💊 ВЕТКА АПТЕКИ
        # =====================================================
        if prefix == "apt":
            lpu_name = data.get("lpu_name")

            report_id = await reportsDB.save_apothecary_report(
                user=user_name,
                district=district_name,
                road=road_name,
                lpu=lpu_name,
                comment=data.get("comms", "-")
            )

            quantities = data.get("final_quantities", {})
            items_to_save = []

            for med_id, val in quantities.items():
                med_name = prep_map.get(med_id) or prep_map.get(str(med_id)) or f"ID {med_id}"

                if isinstance(val, dict):
                    req = val.get('req', 0)
                    rem = val.get('rem', 0)
                else:
                    req = "0"
                    rem = str(val)

                items_to_save.append((med_name, req, rem))

            await reportsDB.save_apothecary_preps(report_id, items_to_save)
            success_text = f"✅ <b>Отчёт по аптеке «{lpu_name}» сохранён!</b>"

        # =====================================================
        # 👨‍⚕️ ВЕТКА ВРАЧА
        # =====================================================
        elif prefix == "doc":
            report_id = await reportsDB.save_main_report(
                user=user_name,
                district=district_name,
                road=road_name,
                lpu=data.get("lpu_name"),
                doctor_name=data.get("doc_name"),
                doctor_spec=data.get("doc_spec"),
                doctor_number=data.get("doc_num", "Unknown"),
                term=data.get("term"),
                comment=data.get("comms", "-")
            )

            await reportsDB.save_preps(report_id, selected_names_list)
            success_text = "✅ <b>Отчёт по врачу сохранён!</b>"

        else:
            await callback.message.answer(f"⚠️ Ошибка: Не удалось определить тип отчета (данные отсутствуют).")
            return

        # =====================================================
        # 🏁 ФИНАЛ
        # =====================================================

        await callback.message.edit_text(success_text)
        kb = await get_main_menu_inline(callback.from_user.id)
        await callback.message.answer("Что делаем дальше?", reply_markup=kb)
        await state.clear()

    except Exception as e:
        logger.critical(f"Error saving report: {e}")
        await callback.message.answer(f"❌ Ошибка при сохранении: {e}")
        await callback.answer()