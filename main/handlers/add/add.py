from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, ReplyKeyboardRemove
from aiogram.fsm.context import FSMContext

from loader import pharmacyDB
from storage.temp_data import TempDataManager

# Ensure these states are defined in your project
from states.add.add_state import AddDoctor, AddPharmacy
from states.add.prescription_state import PrescriptionFSM

from keyboard.inline.inline_buttons import (
    get_lpu_inline,
    get_spec_inline
)

from utils.text import text_utils
from utils.logger.logger_config import logger

router = Router()


# ============================================================
# 🚫 GENERIC CANCEL HANDLER (Best Practice)
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
    """Starts the add process for LPU or Doctor."""
    await callback.message.edit_reply_markup(reply_markup=None)

    # Safely unpack data
    try:
        _, prefix = callback.data.split("_")
    except ValueError:
        logger.error(f"Invalid callback data: {callback.data}")
        await callback.answer("Error", show_alert=True)
        return

    if prefix == "lpu":
        await callback.message.edit_text("🏥 <b>Добавление ЛПУ</b>\nВведите название:")
        await state.set_state(AddPharmacy.waiting_for_name)

    elif prefix == "doc":
        await callback.message.edit_text("👨‍⚕️ <b>Добавление врача</b>\nВведите ФИО врача:")
        await state.set_state(AddDoctor.waiting_for_name)

    else:
        await callback.answer("⚠️ Неизвестный тип", show_alert=True)

    await callback.answer()


# ============================================================
# 🏥 FLOW: ADD PHARMACY (LPU)
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

    # 1. Retrieve Data
    try:
        name, district, road = await TempDataManager.get_many(state, "lpu_name", "district", "road")
    except Exception as e:
        logger.error(f"State data missing: {e}")
        await message.answer("❌ Ошибка данных. Попробуйте начать заново.")
        await state.clear()
        return

    # 2. Database Operation
    try:
        await pharmacyDB.add_lpu(road, name, url)
        logger.info(f"✅ Added LPU: {name} (Road: {road})")

        # 3. Success & Reset
        keyboard = await get_lpu_inline(state, district, road)
        await message.answer(f"✅ ЛПУ <b>{name}</b> успешно добавлено!", reply_markup=keyboard)

    except Exception as e:
        logger.critical(f"DB Error adding LPU: {e}")
        await message.answer("❌ Ошибка при сохранении в базу данных.")

    finally:
        # CRITICAL: SET STATE IN LPU
        await state.set_state(PrescriptionFSM.choose_lpu)


# ============================================================
# 👨‍⚕️ FLOW: ADD DOCTOR
# ============================================================

# Step 1: Name -> Ask for Spec
@router.message(AddDoctor.waiting_for_name)
async def add_doctor_name(message: Message, state: FSMContext):
    fio = message.text.strip()

    # Save name
    await TempDataManager.set(state, "tp_dr_name", fio)

    # Get specs for keyboard (Assuming you have a function for this)
    # If get_spec_inline() needs arguments, make sure to pass them
    keyboard = await get_spec_inline(state)

    await message.answer(
        f"👤 Врач: <b>{fio}</b>\nТеперь выберите специальность (или напишите текстом):",
        reply_markup=keyboard
    )
    await state.set_state(AddDoctor.waiting_for_spec)


# Step 2a: Spec via Text
@router.message(AddDoctor.waiting_for_spec)
async def add_doctor_spec_text(message: Message, state: FSMContext):
    spec = message.text.strip()

    # WARNING: Your DB expects spec_id (int). If user types text,
    # you might need to handle this (e.g., save as 0 or 'Other').
    # For now, saving as string and assuming DB handles it or it's a temp placeholder.
    await TempDataManager.set(state, "tp_dr_spec", value=spec)

    await message.answer("📱 Введите номер телефона (или 'нет'):")
    await state.set_state(AddDoctor.waiting_for_number)


# Step 2b: Spec via Button
@router.callback_query(AddDoctor.waiting_for_spec, F.data.startswith("main_spec_"))
async def add_doctor_spec_callback(callback: CallbackQuery, state: FSMContext):
    # Extract ID from "main_spec_5" -> "5"
    spec_id = callback.data.split("_")[-1]

    await TempDataManager.set(state, "tp_dr_spec", spec_id)

    # Remove keyboard to prevent double clicks
    await callback.message.edit_reply_markup(reply_markup=None)

    await callback.message.answer("📱 Введите номер телефона (или 'нет'):")
    await state.set_state(AddDoctor.waiting_for_number)
    await callback.answer()


# Step 3: Phone -> Ask for Birthdate
@router.message(AddDoctor.waiting_for_number)
async def add_doctor_num(message: Message, state: FSMContext):
    raw_phone = message.text.strip()

    # 1. Проверка: Хочет ли пользователь пропустить?
    if raw_phone.lower() in ['нет', '-', 'no', 'не знаю']:
        phone = None
        msg = "⏩ Номер пропущен."

        # Сохраняем и идем дальше
        await TempDataManager.set(state, "tp_dr_phone", phone)
        await message.answer(f"{msg}\n\n🎂 Введите дату рождения (ДД.ММ.ГГГГ):")
        await state.set_state(AddDoctor.waiting_for_bd)
        return

    # 2. Проверка валидности номера
    phone = text_utils.validate_phone_number(raw_phone)

    if phone:
        # ✅ УСПЕХ: Номер валиден
        await TempDataManager.set(state, "tp_dr_phone", phone)

        await message.answer(f"✅ Номер сохранён: {phone}\n\n🎂 Введите дату рождения (ДД.ММ.ГГГГ):")
        # Переходим к следующему шагу
        await state.set_state(AddDoctor.waiting_for_bd)
    else:
        # ❌ ОШИБКА: Формат неверный -> ПОВТОРЯЕМ ВОПРОС
        await message.answer(
            "⚠️ <b>Неверный формат номера!</b>\n"
            "Пожалуйста, введите номер в формате: <code>+77011234567</code>\n"
            "Или отправьте '<b>-</b>', чтобы пропустить этот шаг."
        )
        # ⛔️ ВАЖНО: Мы НЕ меняем состояние и делаем return,
        # чтобы бот остался ждать ввод номера.
        return


# Step 4: Birthdate -> Save to DB
@router.message(AddDoctor.waiting_for_bd)
async def add_doctor_bd(message: Message, state: FSMContext):
    raw_date = message.text.strip()
    birthdate = None

    # 1. Проверка: Хочет ли пользователь пропустить?
    if raw_date.lower() in ['нет', '-', 'no', 'не знаю']:
        birthdate = None
        # Не делаем return, просто идем дальше сохранять с birthdate=None

    # 2. Проверка валидности даты
    else:
        # validate_date возвращает строку (если ок) или None (если ошибка)
        birthdate = text_utils.validate_date(raw_date)

        if not birthdate:
            # ❌ ОШИБКА: Формат неверный -> ПОВТОРЯЕМ ВОПРОС
            await message.answer(
                "⚠️ <b>Неверный формат даты!</b>\n"
                "Введите дату в формате: <code>ДД.ММ.ГГГГ</code> (например: 25.01.1990)\n"
                "Или отправьте '<b>Нет</b>', чтобы пропустить."
            )
            # ⛔️ Return останавливает функцию, бот остается в том же состоянии
            return

    # --- Если мы дошли сюда, значит дата валидна ИЛИ пропущена ---

    # 3. Retrieve all needed data
    try:
        lpu_id, name, spec, phone = await TempDataManager.get_many(
            state, "lpu_id", "tp_dr_name", "tp_dr_spec", "tp_dr_phone"
        )
    except Exception as e:
        logger.error(f"Session data lost: {e}")
        await message.answer("❌ Данные сессии утеряны. Начните заново.")
        await state.clear()
        return

    # 4. Save to DB
    try:
        # Save to DB (birthdate will be a string or None)
        await pharmacyDB.add_doc(lpu_id, name, spec, phone, birthdate)

        logger.info(f"✅ Doctor added: {name}, SpecID: {spec}, BD: {birthdate}")
        await message.answer("✅ <b>Врач успешно добавлен!</b>")

    except Exception as e:
        logger.critical(f"DB Error adding doctor: {e}")
        await message.answer("❌ Не удалось сохранить врача в базу данных.")

    finally:
        # Always clear state at the end of the wizard
        await state.clear()