from aiogram import Router, F, types
from aiogram.types import CallbackQuery, Message, ReplyKeyboardRemove
from aiogram.fsm.context import FSMContext

# 1. Импортируем класс базы для типов
from db.database import BotDB

# 2. Импорт менеджера временных данных
from storage.temp_data import TempDataManager

# 3. Состояния
from states.add.add_state import AddDoctor, AddPharmacy, AddApothecary
from states.add.prescription_state import PrescriptionFSM

# 4. Клавиатуры (Их мы будем чинить следующими!)
from keyboard.inline.inline_buttons import (
    get_doctors_inline,
    get_lpu_inline,
    get_spec_inline,
    get_apothecary_inline
)

# 5. Утилиты
from utils.text import text_utils
from utils.logger.logger_config import logger

router = Router()


# ============================================================
# 🚫 ОТМЕНА ДЕЙСТВИЯ
# ============================================================
@router.message(F.text.casefold() == "отмена")
@router.callback_query(F.data == "cancel")
async def cancel_handler(event: Message | CallbackQuery, state: FSMContext):
    """Позволяет выйти из любого состояния."""
    current_state = await state.get_state()
    if current_state is None:
        return

    await state.clear()

    if isinstance(event, Message):
        await event.answer("❌ Действие отменено.", reply_markup=ReplyKeyboardRemove())
    elif isinstance(event, CallbackQuery):
        # Если есть сообщение, редактируем его
        if event.message:
            await event.message.edit_text("❌ Действие отменено.")
        await event.answer()


# ============================================================
# 1️⃣ ТОЧКА ВХОДА: КНОПКА "ДОБАВИТЬ..."
# ============================================================
@router.callback_query(F.data.startswith("add_"))
async def add_item(callback: CallbackQuery, state: FSMContext):
    """Начинает процесс добавления ЛПУ, Врача или Аптеки."""
    if callback.message:
        await callback.message.edit_reply_markup(reply_markup=None)

    try:
        _, prefix = callback.data.split("_")
    except ValueError:
        await callback.answer("Ошибка данных", show_alert=True)
        return

    # --- ЛПУ (Больница) ---
    if prefix == "lpu":
        await callback.message.edit_text("🏥 <b>Добавление ЛПУ</b>\nВведите название:")
        await state.set_state(AddPharmacy.waiting_for_name)

    # --- ВРАЧ ---
    elif prefix == "doc":
        await callback.message.edit_text("👨‍⚕️ <b>Добавление врача</b>\nВведите ФИО врача:")
        await state.set_state(AddDoctor.waiting_for_name)

    # --- АПТЕКА (Точка продаж) ---
    elif prefix == "apothecary":
        await callback.message.edit_text("💊 <b>Добавление Аптеки</b>\nВведите название аптеки:")
        await state.set_state(AddApothecary.waiting_for_name)

    else:
        await callback.answer("⚠️ Неизвестный тип", show_alert=True)

    await callback.answer()


# ============================================================
# 🏥 FLOW: ДОБАВЛЕНИЕ ЛПУ (БОЛЬНИЦЫ)
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
async def add_lpu_url(message: Message, state: FSMContext, pharmacy_db: BotDB):
    url = message.text.strip()

    try:
        # Получаем данные из сессии
        data = await TempDataManager.get_many(state, "lpu_name", "district", "road")
        name, district_id, road_num = data
    except Exception as e:
        logger.error(f"State data missing: {e}")
        await message.answer("❌ Ошибка данных сессии. Начните заново.")
        await state.clear()
        return

    try:
        # 1. Находим ID маршрута
        real_road_id = await pharmacy_db.get_road_id_by_number(district_id, road_num)

        if not real_road_id:
            await message.answer(f"❌ Ошибка: Маршрут {road_num} не найден в базе.")
            return

        # 2. Сохраняем ЛПУ
        await pharmacy_db.add_lpu(real_road_id, name, url)
        logger.info(f"✅ Added LPU: {name}")

        # 3. Генерируем клавиатуру (Теперь передаем DB внутрь!)
        keyboard = await get_lpu_inline(pharmacy_db, state)

        await message.answer(f"✅ ЛПУ <b>{name}</b> успешно добавлено!", reply_markup=keyboard)

        # Возвращаем пользователя к выбору ЛПУ
        await state.set_state(PrescriptionFSM.choose_lpu)

    except Exception as e:
        logger.critical(f"DB Error adding LPU: {e}")
        await message.answer("❌ Ошибка при сохранении в базу данных.")


# ============================================================
# 💊 FLOW: ДОБАВЛЕНИЕ АПТЕКИ
# ============================================================
@router.message(AddApothecary.waiting_for_name)
async def add_apt_name(message: Message, state: FSMContext):
    name = message.text.strip()
    if len(name) < 2:
        await message.answer("⚠️ Название слишком короткое.")
        return

    await TempDataManager.set(state, "apt_name", name)
    await message.answer("🔗 Отправьте ссылку (URL) на аптеку из 2GIS:")
    await state.set_state(AddApothecary.waiting_for_url)


@router.message(AddApothecary.waiting_for_url)
async def add_apt_url(message: Message, state: FSMContext, pharmacy_db: BotDB):
    url = message.text.strip()

    try:
        data = await TempDataManager.get_many(state, "apt_name", "district", "road")
        name, district_id, road_num = data
    except Exception:
        await message.answer("❌ Данные сессии утеряны.")
        await state.clear()
        return

    try:
        real_road_id = await pharmacy_db.get_road_id_by_number(district_id, road_num)
        if not real_road_id:
            await message.answer("❌ Маршрут не найден.")
            return

        await pharmacy_db.add_apothecary_place(real_road_id, name, url)

        # Передаем DB в клавиатуру
        keyboard = await get_apothecary_inline(pharmacy_db, state)

        await message.answer(f"✅ Аптека <b>{name}</b> успешно добавлена!", reply_markup=keyboard)
        await state.set_state(PrescriptionFSM.choose_apothecary)

    except Exception as e:
        logger.critical(f"DB Error adding Apothecary: {e}")
        await message.answer("❌ Не удалось сохранить аптеку.")


# ============================================================
# 👨‍⚕️ FLOW: ДОБАВЛЕНИЕ ВРАЧА
# ============================================================
@router.message(AddDoctor.waiting_for_name)
async def add_doctor_name(message: Message, state: FSMContext, pharmacy_db: BotDB):
    fio = message.text.strip()
    await TempDataManager.set(state, "tp_dr_name", fio)

    # Передаем DB для получения списка специальностей
    keyboard = await get_spec_inline(pharmacy_db, state)

    await message.answer(
        f"👤 Врач: <b>{fio}</b>\nТеперь выберите специальность:",
        reply_markup=keyboard
    )
    await state.set_state(AddDoctor.waiting_for_spec)


@router.message(AddDoctor.waiting_for_spec)
async def add_doctor_spec_text(message: Message, state: FSMContext):
    # Если пользователь ввел текстом
    spec = message.text.strip()
    await TempDataManager.set(state, "tp_dr_spec", value=spec)
    await message.answer("📱 Введите номер телефона (или 'нет'):")
    await state.set_state(AddDoctor.waiting_for_number)


@router.callback_query(AddDoctor.waiting_for_spec, F.data.startswith("main_spec_"))
async def add_doctor_spec_callback(callback: CallbackQuery, state: FSMContext):
    # Если пользователь выбрал кнопку
    spec_id = callback.data.split("_")[-1]
    await TempDataManager.set(state, "tp_dr_spec", spec_id)

    if callback.message:
        await callback.message.edit_reply_markup(reply_markup=None)

    await callback.message.answer("📱 Введите номер телефона (или 'нет'):")
    await state.set_state(AddDoctor.waiting_for_number)
    await callback.answer()


@router.message(AddDoctor.waiting_for_number)
async def add_doctor_num(message: Message, state: FSMContext):
    raw_phone = message.text.strip()

    if raw_phone.lower() in ['нет', '-', 'no', 'не знаю']:
        phone = None
    else:
        phone = text_utils.validate_phone_number(raw_phone)
        if not phone:
            await message.answer("⚠️ <b>Неверный формат номера!</b>\nПопробуйте: +77011234567")
            return

    await TempDataManager.set(state, "tp_dr_phone", phone)
    await message.answer("🎂 Введите дату рождения (ДД.ММ.ГГГГ):")
    await state.set_state(AddDoctor.waiting_for_bd)


@router.message(AddDoctor.waiting_for_bd)
async def add_doctor_bd(message: Message, state: FSMContext, pharmacy_db: BotDB):
    raw_date = message.text.strip()
    birthdate = None

    if raw_date.lower() not in ['нет', '-', 'no']:
        birthdate = text_utils.validate_date(raw_date)
        if not birthdate:
            await message.answer("⚠️ <b>Неверный формат даты!</b>\nПопробуйте: ДД.ММ.ГГГГ")
            return

    try:
        data = await TempDataManager.get_many(state, "lpu_id", "tp_dr_name", "tp_dr_spec", "tp_dr_phone")
        lpu_id, name, spec, phone = data
    except Exception:
        await message.answer("❌ Данные сессии утеряны.")
        await state.clear()
        return

    try:
        await pharmacy_db.add_doc(lpu_id, name, spec, phone, birthdate)

        # Передаем DB для обновления списка врачей
        keyboard = await get_doctors_inline(pharmacy_db, state)

        logger.info(f"✅ Doctor added: {name}")
        await message.answer("✅ <b>Врач успешно добавлен!</b>", reply_markup=keyboard)

        # Возвращаем пользователя к выбору врача
        await state.set_state(PrescriptionFSM.choose_doctor)

    except Exception as e:
        logger.critical(f"DB Error adding doctor: {e}")
        await message.answer("❌ Не удалось сохранить врача.")