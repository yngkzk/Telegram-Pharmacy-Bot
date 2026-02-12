from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext

# Импорты БД и утилит
from db.database import BotDB
from storage.temp_data import TempDataManager
from utils.logger.logger_config import logger

# Импорты клавиатур
from keyboard.inline.inline_buttons import get_lpu_inline, get_apothecary_inline, get_doctors_inline

# 🔥 ИМПОРТЫ ТВОИХ СОСТОЯНИЙ
# Обрати внимание: AddPharmacy мы используем для ЛПУ (Больниц)
from states.add.add_state import AddDoctor, AddPharmacy, AddApothecary
from states.add.prescription_state import PrescriptionFSM

router = Router()


# ==========================================
# 🏥 ДОБАВЛЕНИЕ ЛПУ (Больницы) -> используем AddPharmacy
# ==========================================

@router.callback_query(F.data == "add_lpu")
async def start_add_lpu(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("✍️ Введите название нового ЛПУ (Больницы):")
    await state.set_state(AddPharmacy.waiting_for_name)
    await callback.answer()


@router.message(AddPharmacy.waiting_for_name)
async def process_lpu_name(message: types.Message, state: FSMContext):
    name = message.text.strip()
    await state.update_data(new_place_name=name)
    await message.answer("🔗 Введите ссылку на 2ГИС (или отправьте «-», если ссылки нет):")
    await state.set_state(AddPharmacy.waiting_for_url)


@router.message(AddPharmacy.waiting_for_url)
async def process_lpu_final(message: types.Message, state: FSMContext, pharmacy_db: BotDB):
    url_text = message.text.strip()
    final_url = "" if url_text == "-" else url_text

    data = await TempDataManager.get_all(state)
    name = data.get("new_place_name")

    # Восстановление маршрута
    road_id_db = data.get("road_id_db")
    if not road_id_db:
        district = data.get("district")
        road_num = data.get("road")
        road_id_db = await pharmacy_db.get_road_id_by_number(district, road_num)

    if not road_id_db:
        await message.answer("❌ Ошибка: Маршрут потерян. Начните сначала.")
        await state.clear()
        return

    try:
        await pharmacy_db.add_lpu(road_id_db, name, final_url)
        logger.info(f"✅ Added LPU: {name}")

        await message.answer(f"✅ ЛПУ <b>«{name}»</b> успешно добавлено!")

        # Обновляем список
        district_id = data.get("district")
        road_num = data.get("road")
        keyboard = await get_lpu_inline(pharmacy_db, state, district_id, road_num)

        await message.answer("Выберите ЛПУ из списка:", reply_markup=keyboard)

        # 🔥 Возвращаем состояние выбора ЛПУ
        await state.set_state(PrescriptionFSM.picking_lpu)

    except Exception as e:
        logger.critical(f"DB Error adding LPU: {e}")
        await message.answer("❌ Ошибка при добавлении в базу данных.")


# ==========================================
# 💊 ДОБАВЛЕНИЕ АПТЕКИ -> используем AddApothecary
# ==========================================

@router.callback_query(F.data == "add_apothecary")
async def start_add_apothecary(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("✍️ Введите название новой Аптеки:")
    await state.set_state(AddApothecary.waiting_for_name)
    await callback.answer()


@router.message(AddApothecary.waiting_for_name)
async def process_apothecary_name(message: types.Message, state: FSMContext):
    name = message.text.strip()
    await state.update_data(new_place_name=name)
    await message.answer("🔗 Введите ссылку на 2ГИС (или отправьте «-», если ссылки нет):")
    await state.set_state(AddApothecary.waiting_for_url)


@router.message(AddApothecary.waiting_for_url)
async def process_apothecary_final(message: types.Message, state: FSMContext, pharmacy_db: BotDB):
    url_text = message.text.strip()
    final_url = "" if url_text == "-" else url_text

    data = await TempDataManager.get_all(state)
    name = data.get("new_place_name")

    road_id_db = data.get("road_id_db")
    if not road_id_db:
        district = data.get("district")
        road_num = data.get("road")
        road_id_db = await pharmacy_db.get_road_id_by_number(district, road_num)

    if not road_id_db:
        await message.answer("❌ Ошибка: Маршрут потерян.")
        await state.clear()
        return

    try:
        await pharmacy_db.add_apothecary_place(road_id_db, name, final_url)
        logger.info(f"✅ Added Apothecary: {name}")

        await message.answer(f"✅ Аптека <b>«{name}»</b> добавлена!")

        district_id = data.get("district")
        road_num = data.get("road")
        keyboard = await get_apothecary_inline(pharmacy_db, state, district_id, road_num)

        await message.answer("Выберите аптеку:", reply_markup=keyboard)

        # 🔥 Возвращаем состояние выбора ЛПУ (потому что аптеки тоже там)
        await state.set_state(PrescriptionFSM.picking_lpu)

    except Exception as e:
        logger.critical(f"DB Error adding Apothecary: {e}")
        await message.answer(f"❌ Ошибка базы данных: {e}")


# ==========================================
# 👨‍⚕️ ДОБАВЛЕНИЕ ВРАЧА -> используем AddDoctor
# ==========================================

# 1. Старт: Спрашиваем имя
@router.callback_query(F.data == "add_doc")
async def start_add_doc(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("✍️ Введите <b>ФИО врача</b>:")
    # Используем состояние из твоего файла
    await state.set_state(AddDoctor.waiting_for_name)
    await callback.answer()


# 2. Имя -> Спрашиваем специальность
@router.message(AddDoctor.waiting_for_name)
async def process_doc_name(message: types.Message, state: FSMContext):
    name = message.text.strip()
    await state.update_data(new_doc_name=name)

    await message.answer("🩺 Введите <b>специальность</b> (например: Терапевт):")
    await state.set_state(AddDoctor.waiting_for_spec)


# 3. Специальность -> Спрашиваем телефон
@router.message(AddDoctor.waiting_for_spec)
async def process_doc_spec(message: types.Message, state: FSMContext):
    spec = message.text.strip()
    await state.update_data(new_doc_spec=spec)

    await message.answer("📱 Введите <b>номер телефона</b> (или отправьте «-», если номера нет):")
    # Твой следующий шаг в AddDoctor - это waiting_for_number
    await state.set_state(AddDoctor.waiting_for_number)


# 4. Телефон -> Сохраняем (Пропускаем ДР и Подтверждение для скорости)
@router.message(AddDoctor.waiting_for_number)
async def process_doc_final(message: types.Message, state: FSMContext, pharmacy_db: BotDB):
    phone = message.text.strip()
    if phone == "-":
        phone = None

    # Достаем данные (Нам нужен ID больницы!)
    data = await TempDataManager.get_all(state)
    lpu_id = data.get("lpu_id")

    name = data.get("new_doc_name")
    spec = data.get("new_doc_spec")

    if not lpu_id:
        await message.answer("❌ Ошибка: Неизвестно, в какую больницу добавлять врача. Начните выбор заново.")
        await state.clear()
        return

    try:
        # Добавляем врача в БД
        # (birthdate=None, так как мы пропустили waiting_for_bd для простоты)
        await pharmacy_db.add_doc(lpu_id, name, spec, phone, None)
        logger.info(f"✅ Added Doctor: {name} to LPU {lpu_id}")

        await message.answer(f"✅ Врач <b>{name}</b> успешно добавлен!")

        # Строим обновленный список врачей для этой больницы
        keyboard = await get_doctors_inline(pharmacy_db, state, lpu_id=int(lpu_id))

        await message.answer("👨‍⚕️ Выберите врача из списка:", reply_markup=keyboard)

        await state.set_state(PrescriptionFSM.picking_doc)

    except Exception as e:
        logger.critical(f"DB Error adding Doctor: {e}")
        await message.answer(f"❌ Ошибка базы данных: {e}")