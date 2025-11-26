from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, ReplyKeyboardRemove
from aiogram.fsm.context import FSMContext

from loader import pharmacyDB
from storage.temp_data import TempDataManager

from states.add.add_state import AddDoctor, AddPharmacy
from keyboard.inline.inline_buttons import (
    get_lpu_inline,
    get_doctors_inline,
    get_spec_inline,
    get_confirm_inline
)

from utils.text import text_utils
from utils.logger.logger_config import logger


router = Router()


# === 1️⃣ Обработка кнопки "добавить" ===
@router.callback_query(F.data.startswith("add_"))
async def add_item(callback: CallbackQuery, state: FSMContext):
    current_state = await state.get_state()
    logger.info(f"🧭 Текущее состояние: {current_state}")

    await callback.message.edit_reply_markup(reply_markup=None)

    prefix = callback.data.split("_")[1]

    if prefix == "lpu":
        await callback.message.answer("➕ Добавление нового ЛПУ!")
        await callback.message.answer("Введите название нового ЛПУ:")
        await state.set_state(AddPharmacy.waiting_for_name)

    elif prefix == "doc":
        await callback.message.answer("➕ Добавление нового врача!")
        await callback.message.answer("Введите ФИО врача:")
        await state.set_state(AddDoctor.waiting_for_name)

    else:
        await callback.answer("⚠️ Неизвестное место добавления", show_alert=True)

    await callback.answer()


# === 2️⃣ Добавление ЛПУ ===
@router.message(AddPharmacy.waiting_for_name)
async def add_lpu_name(message: Message, state: FSMContext):
    name = message.text.strip()

    await TempDataManager.set(state, "lpu_name", name)

    await message.answer("Отправьте ссылку (URL) для этого ЛПУ через 2gis:")
    await state.set_state(AddPharmacy.waiting_for_url)

    logger.info(f"Пользователь {message.from_user.first_name} — добавляет ЛПУ: {name}")


@router.message(AddPharmacy.waiting_for_url)
async def add_lpu_url(message: Message, state: FSMContext):
    url = message.text.strip()

    name, district, road = await TempDataManager.get_many(state, "lpu_name", "district", "road")

    logger.info(f"Полученные данные: {road, name, url}")

    # async!
    await pharmacyDB.add_lpu(road, name, url)

    logger.info(f"Добавлено ЛПУ: {name} | URL: {url} | Маршрут: {road}")

    keyboard = await get_lpu_inline(state, district, road)
    await message.answer("✅ ЛПУ успешно добавлено!", reply_markup=keyboard)


# === Подтверждение ФИО врача ===
@router.message(AddDoctor.waiting_for_name)
async def add_doctor_confirmation(message: Message, state: FSMContext):
    fio = message.text.strip()

    await TempDataManager.set(state, "tp_dr_name", fio)
    await state.set_state(AddDoctor.waiting_for_spec)

    logger.info(f"ФИО врача: {fio}")

    await message.answer(
        f"Вы ввели ФИО:\n{text_utils.check_name(fio)}\nПодтвердите действие.",
        reply_markup=get_confirm_inline()
    )


# === Выбор специальности врача текстом ===
@router.message(AddDoctor.waiting_for_spec)
async def add_doctor_spec_text(message: Message, state: FSMContext):
    spec = message.text.strip()

    await TempDataManager.set(state, "tp_dr_spec", value=spec)
    await state.set_state(AddDoctor.waiting_for_number)

    district, road, lpu, lpu_id = await TempDataManager.get_many(
        state, "district", "road", "lpu_name", "lpu_id"
    )
    doctor_name = await TempDataManager.get(state, "tp_dr_name")

    logger.info(f"Врач: {doctor_name}, спец: {spec}, ЛПУ: {lpu}")

    await message.answer("Введите номер телефона врача (или 'нет').")


# === Выбор специальности врача через inline-кнопки ===
@router.callback_query(F.data.startswith("main_spec_"))
async def add_doctor_spec_callback(callback: CallbackQuery, state: FSMContext):
    spec = callback.data.replace("main_spec_", "").strip()

    await TempDataManager.set(state, "tp_dr_spec", spec)
    await state.set_state(AddDoctor.waiting_for_number)

    await callback.message.answer("Введите номер телефона врача (или 'нет').")
    await callback.answer()


# === Получаем номер врача ===
@router.message(AddDoctor.waiting_for_number)
async def add_doctor_num(message: Message, state: FSMContext):
    phone = text_utils.validate_phone_number(message.text.strip())

    await TempDataManager.set(state, "tp_dr_phone", phone)
    await state.set_state(AddDoctor.waiting_for_bd)

    logger.info(f"Номер сохранён: {phone}")

    if phone is None:
        await message.answer("☎️ Номер не распознан. Продолжаем без него.")
    else:
        await message.answer(f"☎️ Номер сохранён: {phone}")

    await message.answer("Введите дату рождения врача! Формат: 17.01.2000")


# === Получаем дату рождения и добавляем врача ===
@router.message(AddDoctor.waiting_for_bd)
async def add_doctor_bd(message: Message, state: FSMContext):
    birthdate = text_utils.validate_date(message.text)

    await TempDataManager.set(state, "tp_dr_bd", birthdate)

    logger.info(f"Дата рождения: {birthdate}")

    if birthdate is None:
        await message.answer("⚠️ Дата не распознана. Продолжаем без неё.")
    else:
        await message.answer(f"🎂 Дата сохранена: {birthdate}")

    # получаем все данные
    lpu_id, doctor_name, spec_id, phone = await TempDataManager.get_many(
        state,
        "lpu_id",
        "tp_dr_name",
        "tp_dr_spec",
        "tp_dr_phone"
    )

    # async!
    await pharmacyDB.add_doc(lpu_id, doctor_name, spec_id, phone, birthdate)

    await message.answer("✅ Врач успешно добавлен в систему!")
    await state.clear()
