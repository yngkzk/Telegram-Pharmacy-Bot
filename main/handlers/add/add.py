from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

from loader import pharmacyDB
from numpy.f2py.cfuncs import callbacks
from pandas.core.common import temp_setattr
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
    await state.update_data({"new_lpu_name": name})
    await message.answer("Отправьте ссылку (URL) для этого ЛПУ:")
    await state.set_state(AddState.waiting_for_url)


@router.message(AddPharmacy.waiting_for_url)
async def add_lpu_url(message: Message, state: FSMContext):
    url = message.text.strip()
    data = await state.get_data()

    district, road = await TempDataManager.get_by_mode(state, mode=2)

    # Добавляем в БД
    pharmacyDB.add_lpu(district, road, data["new_lpu_name"], url)

    # Обновляем клавиатуру
    keyboard = await get_lpu_inline(state, district, road)
    await message.answer("✅ ЛПУ успешно добавлено!", reply_markup=keyboard)


# === Подтвердить добавление врача ===
@router.message(AddDoctor.waiting_for_name)
async def add_doctor_confirmation(message: Message, state: FSMContext):
    fio = message.text.strip()

    await TempDataManager.set(state, key="tp_dr_name", value=fio)
    await state.set_state(AddDoctor.waiting_for_spec)

    logger.info(f"Результат в add_doctor_confirm - {fio}")
    await message.answer(f"Вы ввели ФИО: \n{text_utils.check_name(fio)}, \nподтвердите действие.",
                         reply_markup=get_confirm_inline())

# === Получаем специальность врача ===
@router.message(AddDoctor.waiting_for_spec)
@router.callback_query(F.data.startswith("main_spec_"))
async def add_doctor_spec(event: Message | CallbackQuery, state: FSMContext):
    """
    Обрабатывает выбор/ввод специальности врача.
    Работает как на сообщение, так и на callback от inline-кнопок.
    """
    await event.answer()
    doctor_name = await TempDataManager.get(state, key="tp_dr_name")

    # Определяем, пришло ли это сообщение или callback
    if isinstance(event, CallbackQuery):
        spec = event.data.replace("main_spec_", "").strip()
        send = event.message
    else:
        spec = event.text.strip()
        send = event

    # Получаем LPU из FSM
    district, road, lpu, lpu_id = await TempDataManager.get_many(state, "district", "road", "lpu_name", "lpu_id")

    # Добавляем врача в базу
    # add_doctor_to_db(doctor_name, spec, lpu)

    # Для отладки
    logger.info(f"✅ Добавлен врач: {doctor_name}, спец: {spec}, LPU: {lpu}")
    logger.info(f"District - {district}, Road - {road}, lpu - {lpu}")

    # Показываем обновлённый список врачей
    keyboard = await get_doctors_inline(state, lpu_id)
    await send.answer("✅ Врач успешно добавлен!", reply_markup=keyboard)
