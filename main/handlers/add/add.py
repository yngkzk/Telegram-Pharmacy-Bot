from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, ReplyKeyboardRemove
from aiogram.fsm.context import FSMContext

from loader import pharmacyDB
from storage.temp_data import TempDataManager

# Ensure AddApothecary is defined in states/add/add_state.py
from states.add.add_state import AddDoctor, AddPharmacy, AddApothecary
from states.add.prescription_state import PrescriptionFSM

from keyboard.inline.inline_buttons import (
    get_doctors_inline,
    get_lpu_inline,
    get_spec_inline,
    get_apothecary_inline
)

from utils.text import text_utils
from utils.logger.logger_config import logger

router = Router()


# ============================================================
# 🚫 GENERIC CANCEL HANDLER
# ============================================================
@router.message(F.text.casefold() == "отмена")
@router.callback_query(F.data == "cancel")
async def cancel_handler(event: Message | CallbackQuery, state: FSMContext):
    """Allows user to exit the form at any time."""
    current_state = await state.get_state()
    if current_state is None:
        return

    logger.info(f"Cancelling state {current_state}")
    await state.clear()

    if isinstance(event, Message):
        await event.answer("❌ Действие отменено.", reply_markup=ReplyKeyboardRemove())
    else:
        await event.message.edit_text("❌ Действие отменено.")
        await event.answer()


# ============================================================
# 1️⃣ ENTRY POINT: BUTTON "ADD"
# ============================================================
@router.callback_query(F.data.startswith("add_"))
async def add_item(callback: CallbackQuery, state: FSMContext):
    """Starts the add process for LPU, Doctor, or Apothecary (Pharmacy)."""
    await callback.message.edit_reply_markup(reply_markup=None)

    try:
        _, prefix = callback.data.split("_")

        # 🕵️‍♂️ DEBUG PRINT: Look at your console when you click the button!
        logger.info(f"DEBUG: Received prefix '{prefix}'")

    except ValueError:
        logger.error(f"Invalid callback data: {callback.data}")
        await callback.answer("Error", show_alert=True)
        return

    # --- LPU (Hospital/Clinic) ---
    if prefix == "lpu":
        await callback.message.edit_text("🏥 <b>Добавление ЛПУ</b>\nВведите название:")
        await state.set_state(AddPharmacy.waiting_for_name)

    # --- DOCTOR ---
    elif prefix == "doc":
        await callback.message.edit_text("👨‍⚕️ <b>Добавление врача</b>\nВведите ФИО врача:")
        await state.set_state(AddDoctor.waiting_for_name)

    # --- APOTHECARY (Pharmacy Place) ---
    # Based on DB schema: apothecary table has (road_id, name, url)
    elif prefix == "apothecary":
        await callback.message.edit_text("💊 <b>Добавление Аптеки</b>\nВведите название аптеки:")
        await state.set_state(AddApothecary.waiting_for_name)

    else:
        await callback.answer("⚠️ Неизвестный тип", show_alert=True)

    await callback.answer()


# ============================================================
# 🏥 FLOW: ADD PHARMACY (LPU - Hospital)
# ============================================================
@router.message(AddPharmacy.waiting_for_name)
async def add_lpu_name(message: Message, state: FSMContext):
    name = message.text.strip()
    if len(name) < 3:
        await message.answer("⚠️ Название слишком короткое. Попробуйте еще раз.")
        return

    await TempDataManager.set(state, "lpu_name", name)
    await message.answer("🔗 Отправьте ссылку (URL) из 2GIS:")
    await state.set_state(AddPharmacy.waiting_for_url)


@router.message(AddPharmacy.waiting_for_url)
async def add_lpu_url(message: Message, state: FSMContext):
    url = message.text.strip()

    try:
        # 1. Retrieve the raw data (district ID and road NUMBER)
        # Note: We retrieve "road" (the number 1-7), not the ID yet.
        name = await TempDataManager.get(state, "lpu_name")
        district_id = await TempDataManager.get(state, "district")
        road_num = await TempDataManager.get(state, "road")

    except Exception as e:
        logger.error(f"State data missing: {e}")
        await message.answer("❌ Ошибка данных. Попробуйте начать заново.")
        await state.clear()
        return

    try:
        # 2. LOOKUP: Find the correct database ID for this road
        real_road_id = await pharmacyDB.get_road_id_by_number(district_id, road_num)

        if not real_road_id:
            await message.answer(f"❌ Ошибка: Маршрут {road_num} в районе {district_id} не найден в базе.")
            return

        # 3. Save using the REAL ID
        await pharmacyDB.add_lpu(real_road_id, name, url)
        logger.info(f"✅ Added LPU: {name} (Road Number: {road_num} -> ID: {real_road_id})")

        # 4. Success
        # Note: get_lpu_inline likely needs the district_id and road_num (or id depending on your implementation)
        # If get_lpu_inline uses the ID, pass real_road_id. If it uses the number, pass road_num.
        # Based on your previous code, it likely expects the ID for querying:
        keyboard = await get_lpu_inline(state, district_id, real_road_id)

        await message.answer(f"✅ ЛПУ <b>{name}</b> успешно добавлено!", reply_markup=keyboard)

    except Exception as e:
        logger.critical(f"DB Error adding LPU: {e}")
        await message.answer("❌ Ошибка при сохранении в базу данных.")

    finally:
        await state.set_state(PrescriptionFSM.choose_lpu)




# ============================================================
# 💊 FLOW: ADD APOTHECARY (Pharmacy Place)
# ============================================================
# Matches DB Table: apothecary (road_id, name, url)

@router.message(AddApothecary.waiting_for_name)
async def add_apt_name(message: Message, state: FSMContext):
    name = message.text.strip()
    if len(name) < 2:
        await message.answer("⚠️ Название слишком короткое.")
        return

    await TempDataManager.set(state, "apt_name", name)
    # Since DB asks for URL (like LPU), we ask for it here
    await message.answer("🔗 Отправьте ссылку (URL) на аптеку из 2GIS:")
    await state.set_state(AddApothecary.waiting_for_url)


@router.message(AddApothecary.waiting_for_url)
async def add_apt_url(message: Message, state: FSMContext):
    url = message.text.strip()

    try:
        # 1. Retrieve Data
        # 'road' usually holds the NUMBER (1-7), not the DB ID
        name = await TempDataManager.get(state, "apt_name")
        district_id = await TempDataManager.get(state, "district")
        road_num = await TempDataManager.get(state, "road")
    except Exception as e:
        logger.error(f"Session data lost: {e}")
        await message.answer("❌ Данные сессии утеряны.")
        await state.clear()
        return

    try:
        # 2. LOOKUP: Resolve the Real Road ID
        # (Using the method we added to pharmacyDB earlier)
        real_road_id = await pharmacyDB.get_road_id_by_number(district_id, road_num)

        if not real_road_id:
            await message.answer(f"❌ Ошибка: Маршрут {road_num} в районе {district_id} не найден в базе.")
            return

        # 3. Save using the REAL ID
        await pharmacyDB.add_apothecary_place(real_road_id, name, url)

        # 4. Refresh List
        # Ensure get_apothecary_inline uses the real_road_id
        keyboard = await get_apothecary_inline(state, district_id, road_num)

        await message.answer(f"✅ Аптека <b>{name}</b> успешно добавлена!", reply_markup=keyboard)

    except Exception as e:
        logger.critical(f"DB Error adding Apothecary: {e}")
        await message.answer("❌ Не удалось сохранить аптеку.")

    finally:
        await state.set_state(PrescriptionFSM.choose_apothecary)


# ============================================================
# 👨‍⚕️ FLOW: ADD DOCTOR (Person)
# ============================================================
@router.message(AddDoctor.waiting_for_name)
async def add_doctor_name(message: Message, state: FSMContext):
    fio = message.text.strip()
    await TempDataManager.set(state, "tp_dr_name", fio)
    keyboard = await get_spec_inline(state)
    await message.answer(
        f"👤 Врач: <b>{fio}</b>\nТеперь выберите специальность:",
        reply_markup=keyboard
    )
    await state.set_state(AddDoctor.waiting_for_spec)


@router.message(AddDoctor.waiting_for_spec)
async def add_doctor_spec_text(message: Message, state: FSMContext):
    spec = message.text.strip()
    await TempDataManager.set(state, "tp_dr_spec", value=spec)
    await message.answer("📱 Введите номер телефона (или 'нет'):")
    await state.set_state(AddDoctor.waiting_for_number)


@router.callback_query(AddDoctor.waiting_for_spec, F.data.startswith("main_spec_"))
async def add_doctor_spec_callback(callback: CallbackQuery, state: FSMContext):
    spec_id = callback.data.split("_")[-1]
    await TempDataManager.set(state, "tp_dr_spec", spec_id)
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer("📱 Введите номер телефона (или 'нет'):")
    await state.set_state(AddDoctor.waiting_for_number)
    await callback.answer()


@router.message(AddDoctor.waiting_for_number)
async def add_doctor_num(message: Message, state: FSMContext):
    raw_phone = message.text.strip()

    if raw_phone.lower() in ['нет', '-', 'no', 'не знаю']:
        phone = None
        msg = "⏩ Номер пропущен."
        await TempDataManager.set(state, "tp_dr_phone", phone)
        await message.answer(f"{msg}\n\n🎂 Введите дату рождения (ДД.ММ.ГГГГ):")
        await state.set_state(AddDoctor.waiting_for_bd)
        return

    phone = text_utils.validate_phone_number(raw_phone)

    if phone:
        await TempDataManager.set(state, "tp_dr_phone", phone)
        await message.answer(f"✅ Номер сохранён: {phone}\n\n🎂 Введите дату рождения (ДД.ММ.ГГГГ):")
        await state.set_state(AddDoctor.waiting_for_bd)
    else:
        await message.answer("⚠️ <b>Неверный формат номера!</b>\nПопробуйте: +77011234567")
        return


@router.message(AddDoctor.waiting_for_bd)
async def add_doctor_bd(message: Message, state: FSMContext):
    raw_date = message.text.strip()

    if raw_date.lower() in ['нет', '-', 'no', 'не знаю']:
        birthdate = None
    else:
        birthdate = text_utils.validate_date(raw_date)
        if not birthdate:
            await message.answer("⚠️ <b>Неверный формат даты!</b>\nПопробуйте: ДД.ММ.ГГГГ")
            return

    try:
        lpu_id, name, spec, phone = await TempDataManager.get_many(
            state, "lpu_id", "tp_dr_name", "tp_dr_spec", "tp_dr_phone"
        )
    except Exception as e:
        logger.error(f"Session data lost: {e}")
        await message.answer("❌ Данные сессии утеряны.")
        await state.clear()
        return

    try:
        await pharmacyDB.add_doc(lpu_id, name, spec, phone, birthdate)

        keyboard = await get_doctors_inline(state, lpu_id)

        logger.info(f"✅ Doctor added: {name}")
        await message.answer("✅ <b>Врач успешно добавлен!</b>", reply_markup=keyboard)

    except Exception as e:
        logger.critical(f"DB Error adding doctor: {e}")
        await message.answer("❌ Не удалось сохранить врача.")

    finally:
        await state.set_state(PrescriptionFSM.choose_doctor)