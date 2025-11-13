from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, ReplyKeyboardRemove
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

from loader import pharmacyDB
from storage.temp_data import TempDataManager

from states.add_state import AddDoctor, AddPharmacy
from keyboard.inline_buttons import get_lpu_inline, get_doctors_inline, get_spec_inline, get_confirm_inline

from utils import text_utils
from utils.logger_config import logger


router = Router()

# === 1️⃣ Обработка кнопки "добавить" ===
@router.callback_query(F.data.startswith("add_"))
async def add_item(callback: CallbackQuery, state: FSMContext):
    """
    Добавляет новые кнопки в указанном контексте
    """
    current_state = await state.get_state()
    logger.info(f"🧭 Текущее состояние: {current_state}")

    # Убираю клавиатуру
    await callback.message.edit_reply_markup(reply_markup=None)

    prefix = callback.data.split("_")[1]  # например "lpu" или "doc"
    # Определяем, что добавить
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
    await TempDataManager.set(state, key="lpu_name", value=name)
    await message.answer("Отправьте ссылку (URL) для этого ЛПУ через 2gis:")
    await state.set_state(AddPharmacy.waiting_for_url)

    logger.info(f"Пользователь {message.from_user.first_name} - Добавляет ЛПУ - Название {name}")


@router.message(AddPharmacy.waiting_for_url)
async def add_lpu_url(message: Message, state: FSMContext):
    url = message.text.strip()

    name, district, road = await TempDataManager.get_many(state, "lpu_name", "district", "road")

    logger.info(f"Полученные данные {road, name, url}")

    # Добавляем в БД
    pharmacyDB.add_lpu(road, name, url)

    logger.info(f"Пользователь {message.from_user.first_name} -"
                f" Добавил новое ЛПУ - "
                f"Название - {name}, "
                f"Ссылка - {url}"
                f"Маршрут - {road}")

    # Обновляем клавиатуру
    keyboard = await get_lpu_inline(state, district, road)
    await message.answer("✅ ЛПУ успешно добавлено!", reply_markup=keyboard)


# === Подтверждение ФИО врача ===
@router.message(AddDoctor.waiting_for_name)
async def add_doctor_confirmation(message: Message, state: FSMContext):
    fio = message.text.strip()

    await TempDataManager.set(state, key="tp_dr_name", value=fio)
    await state.set_state(AddDoctor.waiting_for_spec)

    logger.info(f"Результат в add_doctor_confirm - {fio}")
    await message.answer(
        f"Вы ввели ФИО:\n{text_utils.check_name(fio)}\nПодтвердите действие.",
        reply_markup=get_confirm_inline()
    )


# === Ввод специальности врача (текстом) ===
@router.message(AddDoctor.waiting_for_spec)
async def add_doctor_spec_text(message: Message, state: FSMContext):
    spec = message.text.strip()
    await TempDataManager.set(state, key="tp_dr_spec", value=spec)
    await state.set_state(AddDoctor.waiting_for_number)

    district, road, lpu, lpu_id = await TempDataManager.get_many(state, "district", "road", "lpu_name", "lpu_id")
    doctor_name = await TempDataManager.get(state, "tp_dr_name")

    logger.info(f"✅ Добавлен врач: {doctor_name}, спец: {spec}, LPU: {lpu}")
    await message.answer("Введите номер телефона врача (или 'нет').")


# === Выбор специальности врача через inline-кнопки ===
@router.callback_query(F.data.startswith("main_spec_"))
async def add_doctor_spec_callback(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    spec = callback.data.replace("main_spec_", "").strip()

    await TempDataManager.set(state, key="tp_dr_spec", value=spec)
    await state.set_state(AddDoctor.waiting_for_number)

    district, road, lpu, lpu_id = await TempDataManager.get_many(state, "district", "road", "lpu_name", "lpu_id")
    doctor_name = await TempDataManager.get(state, "tp_dr_name")

    logger.info(f"✅ Добавлен врач: {doctor_name}, спец: {spec}, LPU: {lpu}")
    await callback.message.answer("Введите номер телефона врача (или 'нет').")


# === Получаем номер врача ===
@router.message(AddDoctor.waiting_for_number)
async def add_doctor_num(message: Message, state: FSMContext):
    raw_input = message.text.strip()
    phone = text_utils.validate_phone_number(raw_input)

    await TempDataManager.set(state, key="tp_dr_phone", value=phone)
    logger.info(f"Сохранён номер телефона: {phone}"
                f"\nТип данных: {type(phone)}")

    if phone is None:
        await message.answer("☎️ Номер не распознан или отсутствует. Продолжаем без него.")
    else:
        await message.answer(f"✅ Номер сохранён: {phone}")

    # Вытаскиваем данные
    lpu_id, doctor_name, spec_id, number = await TempDataManager.get_many(state, "lpu_id",
                                                                          "tp_dr_name",
                                                                          "tp_dr_spec",
                                                                          "tp_dr_phone")

    # Добавляем врача в БД
    pharmacyDB.add_doc(lpu_id, doctor_name, spec_id, number)

    # Дальнейшие действия
    await message.answer("✅ Врач успешно добавлен в систему!")
    await state.clear()