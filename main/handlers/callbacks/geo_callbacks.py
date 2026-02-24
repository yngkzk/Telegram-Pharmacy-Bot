from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext

# Импорты репозиториев для DI
from infrastructure.database.repo.pharmacy_repo import PharmacyRepository

# Импорты состояний
from states.add.prescription_state import PrescriptionFSM

# Импорты клавиатур
from keyboard.inline import inline_buttons

router = Router()

# ============================================================
# 🗺 НАВИГАЦИЯ (Выбор района)
# ============================================================

@router.callback_query(F.data.contains("district_"))
async def process_district(
        callback: types.CallbackQuery, 
        state: FSMContext, 
        pharmacy_repo: PharmacyRepository
):
    is_pharmacy = callback.data.startswith("a_district_")

    try:
        district_id = int(callback.data.split("_")[-1])
    except ValueError:
        return await callback.answer("Ошибка: неверный ID района")

    # 1. Используем DI репозиторий (никаких async for session!)
    district = await pharmacy_repo.get_district_by_id(district_id)

    if not district:
        return await callback.answer("Район не найден", show_alert=True)

    # 2. 🔥 ВАЖНО: Переходим на нативный FSMContext
    # Можно передавать сразу несколько ключей
    await state.update_data(
        district_id=district_id,
        district_name=district.name
    )

    prefix = "a_road" if is_pharmacy else "road"
    roads_fixed = [{"id": i, "road_num": i} for i in range(1, 8)]

    kb = await inline_buttons.get_road_inline(roads_fixed, state, prefix=prefix)

    await callback.message.edit_text(
        f"✅ Район: <b>{district.name}</b>\nВыберите номер маршрута:",
        reply_markup=kb
    )
    await callback.answer()


# ============================================================
# 🗺 НАВИГАЦИЯ (Выбор маршрута)
# ============================================================

@router.callback_query(F.data.contains("road_"))
async def process_road(
        callback: types.CallbackQuery, 
        state: FSMContext, 
        pharmacy_repo: PharmacyRepository
):
    is_pharmacy = callback.data.startswith("a_road_")
    road_num = int(callback.data.split("_")[-1])

    # 1. Достаем данные из нативного стейта
    data = await state.get_data()
    district_id = data.get("district_id")
    district_name = data.get("district_name", "Неизвестный район")

    if not district_id:
        return await callback.answer("Ошибка: выберите район заново", show_alert=True)

    # 2. Сохраняем номер маршрута
    await state.update_data(road_num=road_num)

    # 3. Ищем road_id через DI репозиторий
    road_id = await pharmacy_repo.get_road_id_by_data(district_id, road_num)

    if not road_id:
        return await callback.answer(f"Маршрут №{road_num} не найден в базе.", show_alert=True)

    # Сохраняем road_id для следующих шагов
    await state.update_data(road_id=road_id)

    # 4. Загружаем объекты и ставим стейты
    if is_pharmacy:
        await state.set_state(PrescriptionFSM.choose_apothecary)
        items = await pharmacy_repo.get_apothecaries_by_road(road_id)
        kb = await inline_buttons.get_apothecary_inline(items, state)
        title = "🏪 <b>Аптеки</b>"
    else:
        await state.set_state(PrescriptionFSM.choose_lpu)
        items = await pharmacy_repo.get_lpus_by_road(road_id)
        kb = await inline_buttons.get_lpu_inline(items, state)
        title = "🏥 <b>ЛПУ</b>"

    await callback.message.edit_text(
        f"✅ {district_name} | Маршрут {road_num}\n{title}\nВыберите объект:",
        reply_markup=kb
    )
    await callback.answer()