from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext

# Импорты Новой Базы
from infrastructure.database.db_helper import db_helper
from infrastructure.database.repo.pharmacy_repo import PharmacyRepository
from storage.temp_data import TempDataManager
from utils.logger.logger_config import logger

# Импорты клавиатур
from keyboard.inline.inline_buttons import get_lpu_inline, get_apothecary_inline, get_doctors_inline, get_specs_inline

# Импорты состояний
from states.add.add_state import AddDoctor, AddPharmacy, AddApothecary
from states.add.prescription_state import PrescriptionFSM

router = Router()


# ==========================================
# 🏥 ДОБАВЛЕНИЕ ЛПУ (Больницы)
# ==========================================

@router.callback_query(F.data == "add_lpu")
async def start_add_lpu(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("✍️ Введите название нового ЛПУ (Больницы):")
    await state.set_state(AddPharmacy.waiting_for_name)
    await callback.answer()


@router.message(AddPharmacy.waiting_for_name)
async def process_lpu_name(message: types.Message, state: FSMContext):
    await state.update_data(new_place_name=message.text.strip())
    await message.answer("🔗 Введите ссылку на 2ГИС (или отправьте «-»):")
    await state.set_state(AddPharmacy.waiting_for_url)


@router.message(AddPharmacy.waiting_for_url)
async def process_lpu_final(message: types.Message, state: FSMContext):
    url_text = message.text.strip()
    final_url = None if url_text in ["-", "нет"] else url_text

    data = await state.get_data()
    name = data.get("new_place_name")

    # Берем road_id, который мы сохранили в general_callbacks
    # (Обрати внимание: мы использовали TempData, там ключ 'road_id')
    road_id = await TempDataManager.get(state, "road_id")

    if not road_id:
        await message.answer("❌ Ошибка: Маршрут потерян. Начните сначала.")
        await state.clear()
        return

    async for session in db_helper.get_pharmacy_session():
        repo = PharmacyRepository(session)
        try:
            # 1. Добавляем в БД
            await repo.add_lpu(road_id, name, final_url)
            logger.info(f"✅ Added LPU: {name}")

            await message.answer(f"✅ ЛПУ <b>«{name}»</b> добавлено!")

            # 2. Получаем обновленный список
            items = await repo.get_lpus_by_road(road_id)

            # 3. Рисуем клавиатуру (в новом формате!)
            keyboard = await get_lpu_inline(items, state)

            await message.answer("🏥 Выберите ЛПУ из списка:", reply_markup=keyboard)
            await state.set_state(PrescriptionFSM.choose_lpu)  # Исправил на choose_lpu (как в general_callbacks)

        except Exception as e:
            logger.critical(f"DB Error adding LPU: {e}")
            await message.answer("❌ Ошибка при добавлении.")


# ==========================================
# 💊 ДОБАВЛЕНИЕ АПТЕКИ
# ==========================================

@router.callback_query(F.data == "add_apothecary")
async def start_add_apothecary(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("✍️ Введите название новой Аптеки:")
    await state.set_state(AddApothecary.waiting_for_name)
    await callback.answer()


@router.message(AddApothecary.waiting_for_name)
async def process_ap_name(message: types.Message, state: FSMContext):
    await state.update_data(new_place_name=message.text.strip())
    await message.answer("🔗 Введите ссылку на 2ГИС (или отправьте «-»):")
    await state.set_state(AddApothecary.waiting_for_url)


@router.message(AddApothecary.waiting_for_url)
async def process_ap_final(message: types.Message, state: FSMContext):
    url_text = message.text.strip()
    final_url = None if url_text in ["-", "нет"] else url_text

    data = await state.get_data()
    name = data.get("new_place_name")

    road_id = await TempDataManager.get(state, "road_id")

    if not road_id:
        await message.answer("❌ Маршрут потерян.")
        return

    async for session in db_helper.get_pharmacy_session():
        repo = PharmacyRepository(session)
        try:
            await repo.add_apothecary(road_id, name, final_url)
            logger.info(f"✅ Added Apothecary: {name}")

            await message.answer(f"✅ Аптека <b>«{name}»</b> добавлена!")

            # Обновляем список аптек
            items = await repo.get_apothecaries_by_road(road_id)
            keyboard = await get_apothecary_inline(items, state)

            await message.answer("🏪 Выберите аптеку:", reply_markup=keyboard)
            await state.set_state(PrescriptionFSM.choose_apothecary)

        except Exception as e:
            logger.critical(f"DB Error: {e}")
            await message.answer("Ошибка добавления.")


# ==========================================
# 👨‍⚕️ ДОБАВЛЕНИЕ ВРАЧА
# ==========================================

@router.callback_query(F.data.startswith("add_doctor_"))
async def start_add_doc(callback: types.CallbackQuery, state: FSMContext):
    # Достаем ID ЛПУ прямо из кнопки (мы его туда зашили в get_doctors_inline)
    lpu_id = int(callback.data.split("_")[-1])
    await TempDataManager.set(state, "lpu_id", lpu_id)

    await callback.message.answer("✍️ Введите <b>ФИО врача</b>:")
    await state.set_state(AddDoctor.waiting_for_name)
    await callback.answer()


@router.message(AddDoctor.waiting_for_name)
async def process_doc_name(message: types.Message, state: FSMContext):
    name = message.text.strip()
    await state.update_data(new_doc_name=name)

    async for session in db_helper.get_pharmacy_session():
        repo = PharmacyRepository(session)
        specs = await repo.get_all_specs()

        keyboard = await get_specs_inline(specs)

        await message.answer(
            f"🩺 Выберите специальность врача <b>{name}</b> из списка:\n"
            f"<i>Или напишите новую вручную, и я добавлю её в базу.</i>",
            reply_markup=keyboard
        )
        # Ждем ЛИБО нажатия кнопки, ЛИБО текста
        await state.set_state(AddDoctor.waiting_for_spec)


@router.callback_query(F.data.startswith("spec_"), AddDoctor.waiting_for_spec)
async def process_spec_button(callback: types.CallbackQuery, state: FSMContext):
    spec_id = int(callback.data.split("_")[-1])

    await state.update_data(new_doc_spec_id=spec_id)  # Сохраняем ID!

    await callback.message.edit_text(f"✅ Специальность выбрана.")
    await callback.message.answer("📱 Введите <b>номер телефона</b> (или отправьте «-»):")
    await state.set_state(AddDoctor.waiting_for_number)
    await callback.answer()


@router.message(AddDoctor.waiting_for_spec)
async def process_spec_text(message: types.Message, state: FSMContext):
    spec_name = message.text.strip()

    # Магия: ищем или создаем
    async for session in db_helper.get_pharmacy_session():
        repo = PharmacyRepository(session)
        spec_id = await repo.get_or_create_spec_id(spec_name)

        await state.update_data(new_doc_spec_id=spec_id)  # Сохраняем ID!

        await message.answer(f"✨ Новая специальность <b>«{spec_name}»</b> добавлена в справочник!")
        await message.answer("📱 Введите <b>номер телефона</b> (или отправьте «-»):")
        await state.set_state(AddDoctor.waiting_for_number)


# 4. Финал (Сохранение врача)
@router.message(AddDoctor.waiting_for_number)
async def process_doc_final(message: types.Message, state: FSMContext):
    numb = message.text.strip()
    if numb in ["-", "нет", "."]: phone = None

    data = await state.get_data()
    name = data.get("new_doc_name")
    spec_id = data.get("new_doc_spec_id")  # Берем ID, а не текст

    lpu_id = await TempDataManager.get(state, "lpu_id")

    if not lpu_id:
        await message.answer("❌ Ошибка: ID ЛПУ потерян.")
        return

    async for session in db_helper.get_pharmacy_session():
        repo = PharmacyRepository(session)
        try:
            # Вызываем обновленный метод add_doctor (с spec_id)
            await repo.add_doctor(lpu_id, name, spec_id, numb)

            await message.answer(f"✅ Врач <b>{name}</b> успешно добавлен!")

            # Показываем список
            doctors = await repo.get_doctors_by_lpu(lpu_id)
            keyboard = await get_doctors_inline(
                doctors=doctors,
                lpu_id=lpu_id,
                page=1,
                state=state
            )

            await message.answer("👨‍⚕️ Выберите врача:", reply_markup=keyboard)
            await state.set_state(PrescriptionFSM.choose_doctor)

        except Exception as e:
            logger.critical(f"DB Error adding Doctor: {e}")
            await message.answer(f"❌ Ошибка базы: {e}")