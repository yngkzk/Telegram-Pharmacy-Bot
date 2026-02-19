from contextlib import suppress
from aiogram import Router, types, F
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext

# Импорты БД
from infrastructure.database.db_helper import db_helper
from infrastructure.database.repo.pharmacy_repo import PharmacyRepository

from storage.temp_data import TempDataManager
from states.add.prescription_state import PrescriptionFSM

# 🔥 ИМПОРТЫ ТВОЕЙ СТАРОЙ КЛАВИАТУРЫ
from keyboard.inline.inline_select import build_multi_select_keyboard

# Импорты кнопок навигации
from keyboard.inline.inline_buttons import (
    get_road_inline,
    get_lpu_inline,
    get_apothecary_inline,
    get_doctors_inline,
    get_confirm_inline
)

router = Router()


# ============================================================
# 📥 ВСПОМОГАТЕЛЬНАЯ ФУНКЦИЯ (Адаптация под SQLAlchemy)
# ============================================================
async def ensure_prep_items_loaded(state: FSMContext):
    """
    Загружает список препаратов в TempData для старой клавиатуры.
    """
    items = await TempDataManager.get(state, "prep_items")

    if items is None:
        async for session in db_helper.get_pharmacy_session():
            repo = PharmacyRepository(session)
            all_preps = await repo.get_preps()

            items = []
            prep_map = {}

            for p in all_preps:
                p_id = getattr(p, 'id', None) or p.get('id')
                p_name = getattr(p, 'prep', None) or getattr(p, 'name', None) or p.get('prep')

                if p_id and p_name:
                    items.append((p_id, p_name))
                    prep_map[str(p_id)] = p_name
                    prep_map[int(p_id)] = p_name

            await TempDataManager.set(state, "prep_items", items)
            await TempDataManager.set(state, "prep_map", prep_map)

    return items


# ============================================================
# 1. ВЫБОР РАЙОНА И МАРШРУТА
# ============================================================
@router.callback_query(F.data.startswith("district_"), PrescriptionFSM.picking_district)
@router.callback_query(F.data.startswith("a_district_"), PrescriptionFSM.picking_district)
async def process_district_selection(callback: types.CallbackQuery, state: FSMContext):
    is_pharmacy = callback.data.startswith("a_district_")

    try:
        district_id = int(callback.data.split("_")[-1])
    except ValueError:
        return await callback.answer("Ошибка ID")

    await TempDataManager.set(state, "district_id", district_id)
    district_name = await TempDataManager.get_button_name(state, callback.data) or "Район"
    await TempDataManager.set(state, "district_name", district_name)

    roads_data = [{"road_num": i} for i in range(1, 8)]
    prefix = "a_road" if is_pharmacy else "road"
    kb = await get_road_inline(roads_data, state, prefix=prefix)

    await state.set_state(PrescriptionFSM.picking_road)
    await callback.message.edit_text(
        f"✅ Район: <b>{district_name}</b>\nВыберите маршрут:",
        reply_markup=kb
    )
    await callback.answer()


@router.callback_query(F.data.contains("road_"), PrescriptionFSM.picking_road)
async def process_road_selection(callback: types.CallbackQuery, state: FSMContext):
    is_pharmacy = callback.data.startswith("a_road_")
    try:
        road_num = int(callback.data.split("_")[-1])
    except ValueError:
        return await callback.answer("Ошибка маршрута")

    await TempDataManager.set(state, "road_num", road_num)
    prefix = "apt" if is_pharmacy else "doc"
    await TempDataManager.set(state, "prefix", prefix)

    district_id = await TempDataManager.get(state, "district_id")
    district_name = await TempDataManager.get(state, "district_name")

    async for session in db_helper.get_pharmacy_session():
        repo = PharmacyRepository(session)
        road_id = await repo.get_road_id_by_data(district_id, road_num)

        if not road_id:
            return await callback.answer("Маршрут не найден", show_alert=True)

        await TempDataManager.set(state, "road_id", road_id)

        if is_pharmacy:
            await state.set_state(PrescriptionFSM.choose_apothecary)
            items = await repo.get_apothecaries_by_road(road_id)
            kb = await get_apothecary_inline(items, state)
            title = "🏪 <b>Аптеки</b>"
        else:
            await state.set_state(PrescriptionFSM.choose_lpu)
            items = await repo.get_lpus_by_road(road_id)
            kb = await get_lpu_inline(items, state)
            title = "🏥 <b>ЛПУ</b>"

        await callback.message.edit_text(
            f"✅ {district_name} | М{road_num}\n{title}\nВыберите объект:",
            reply_markup=kb
        )
    await callback.answer()


# ============================================================
# 2. ВЫБОР ЛПУ (Врачи)
# ============================================================
@router.callback_query(F.data.startswith("lpu_"), PrescriptionFSM.choose_lpu)
async def process_lpu_selection(callback: types.CallbackQuery, state: FSMContext):
    try:
        lpu_id = int(callback.data.split("_")[-1])
    except ValueError:
        return await callback.answer("Ошибка ID ЛПУ")

    await TempDataManager.set(state, "lpu_id", lpu_id)
    lpu_name = await TempDataManager.get_button_name(state, callback.data) or f"ЛПУ #{lpu_id}"
    await TempDataManager.set(state, "lpu_name", lpu_name)

    await state.set_state(PrescriptionFSM.choose_doctor)

    async for session in db_helper.get_pharmacy_session():
        repo = PharmacyRepository(session)
        doctors = await repo.get_doctors_by_lpu(lpu_id)
        keyboard = await get_doctors_inline(doctors, lpu_id=lpu_id, page=1, state=state)

        await callback.message.edit_text(
            f"🏥 <b>{lpu_name}</b>\n👨‍⚕️ Выберите врача:",
            reply_markup=keyboard
        )
    await callback.answer()


# ============================================================
# 3. ВЫБОР АПТЕКИ -> ВОПРОС ПРО ЗАЯВКУ
# ============================================================
@router.callback_query(F.data.startswith("apothecary_"), PrescriptionFSM.choose_apothecary)
async def process_apothecary_selection(callback: types.CallbackQuery, state: FSMContext):
    try:
        apt_id = int(callback.data.split("_")[-1])
    except ValueError:
        return await callback.answer("Ошибка ID Аптеки")

    await TempDataManager.set(state, "lpu_id", apt_id)
    apt_name = await TempDataManager.get_button_name(state, callback.data) or f"Аптека #{apt_id}"
    await TempDataManager.set(state, "apt_name", apt_name)
    await TempDataManager.set(state, "prefix", "apt")

    # 🔥 ОСТАЕМСЯ В СОСТОЯНИИ choose_apothecary (ИСПРАВЛЕНИЕ КОЛЛИЗИИ)
    await state.set_state(PrescriptionFSM.choose_apothecary)

    await callback.message.edit_text(
        f"🏪 <b>{apt_name}</b>\n\n📝 Есть ли заявка на препараты или остатки?",
        reply_markup=get_confirm_inline(mode=False)
    )
    await callback.answer()


# ============================================================
# 4. ОБРАБОТКА "ЕСТЬ ЗАЯВКА" -> ЗАПУСК ТВОЕЙ КЛАВИАТУРЫ
# ============================================================
# 🔥 ЛОВИМ ОТВЕТ ИМЕННО В СОСТОЯНИИ choose_apothecary
@router.callback_query(F.data.in_(["confirm_yes", "confirm_no"]), PrescriptionFSM.choose_apothecary)
async def process_confirmation_step(callback: types.CallbackQuery, state: FSMContext):
    if callback.data == "confirm_no":
        await state.set_state(PrescriptionFSM.pharmacy_comments)
        await callback.message.edit_text("✍️ Напишите комментарий к визиту (или «-»):")
        await callback.answer()
        return

    # Если ДА (Есть заявка)
    items = await ensure_prep_items_loaded(state)
    await TempDataManager.set(state, "selected_items", [])

    # ВЫЗЫВАЕМ ТВОЮ РОДНУЮ КЛАВИАТУРУ
    kb = build_multi_select_keyboard(items, [], "apt")

    await state.set_state(PrescriptionFSM.choose_meds)

    await callback.message.edit_text(
        "💊 <b>Выберите препараты (можно несколько):</b>",
        reply_markup=kb
    )
    await callback.answer()


# ============================================================
# 5. ☑️ ТВОЙ СТАРЫЙ TOGGLE (Переключение галочек)
# ============================================================
@router.callback_query(F.data.startswith("select_"), PrescriptionFSM.choose_meds)
async def toggle_selection(callback: types.CallbackQuery, state: FSMContext):
    try:
        _, prefix, option_id = callback.data.split("_")
        option_id = int(option_id)
    except ValueError:
        return await callback.answer("Ошибка данных кнопки")

    items = await TempDataManager.get(state, "prep_items")
    if not items:
        items = await ensure_prep_items_loaded(state)

    selected = await TempDataManager.get(state, "selected_items") or []

    if option_id in selected:
        selected.remove(option_id)
    else:
        selected.append(option_id)

    await TempDataManager.set(state, "selected_items", selected)
    new_keyboard = build_multi_select_keyboard(items, selected, prefix)

    with suppress(TelegramBadRequest):
        await callback.message.edit_reply_markup(reply_markup=new_keyboard)

    await callback.answer()


# ============================================================
# 6. СБРОС ВЫБОРА (RESET)
# ============================================================
@router.callback_query(F.data == "reset_selection", PrescriptionFSM.choose_meds)
async def reset_selection(callback: types.CallbackQuery, state: FSMContext):
    items = await ensure_prep_items_loaded(state)
    prefix = await TempDataManager.get(state, "prefix") or "doc"

    await TempDataManager.set(state, "selected_items", [])
    new_keyboard = build_multi_select_keyboard(items, [], prefix)

    with suppress(TelegramBadRequest):
        await callback.message.edit_reply_markup(reply_markup=new_keyboard)

    await callback.answer("🗑 Выбор сброшен")


# ============================================================
# 7. ПОДТВЕРЖДЕНИЕ ВЫБОРА (Кнопка "Готово")
# ============================================================
@router.callback_query(F.data == "confirm_selection", PrescriptionFSM.choose_meds)
async def confirm_selection(callback: types.CallbackQuery, state: FSMContext):
    selected_ids = await TempDataManager.get(state, "selected_items") or []

    if not selected_ids:
        return await callback.answer("⚠️ Выберите хотя бы один препарат!", show_alert=True)

    data = await TempDataManager.get_all(state)
    prefix = data.get("prefix")

    # --- ВРАЧ ---
    if prefix == "doc":
        await state.set_state(PrescriptionFSM.contract_terms)

        prep_map = await TempDataManager.get(state, "prep_map", {})
        names = [prep_map.get(str(i)) or prep_map.get(int(i)) or f"ID {i}" for i in selected_ids]
        names_str = "\n".join([f"• {n}" for n in names])

        await callback.message.edit_text(
            f"✅ <b>Выбрано:</b>\n{names_str}\n\n✍️ Введите условия договора:"
        )

    # --- АПТЕКА ---
    elif prefix == "apt":
        await TempDataManager.set(state, "quantity_queue", list(selected_ids))
        await TempDataManager.set(state, "final_quantities", {})

        await callback.message.edit_text("✅ <b>Список принят.</b>\nПереходим к вводу количества.")
        await ask_next_pharmacy_item(callback.message, state)

    await callback.answer()


# ============================================================
# 8. ВЫБОР ВРАЧА (Обычный)
# ============================================================
@router.callback_query(F.data.startswith("doc_"), PrescriptionFSM.choose_doctor)
async def process_doctor(callback: types.CallbackQuery, state: FSMContext):
    doc_id = int(callback.data.split("_")[-1])
    doc_name = await TempDataManager.get_button_name(state, callback.data) or "Врач"

    await TempDataManager.set(state, "doc_id", doc_id)
    await TempDataManager.set(state, "doc_name", doc_name)
    await TempDataManager.set(state, "prefix", "doc")

    async for session in db_helper.get_pharmacy_session():
        repo = PharmacyRepository(session)

        # 🔥 1. Достаем объект врача из базы
        doctor = await repo.get_doctor_by_id(doc_id)
        doc_spec = "Не указана"

        # 🔥 2. Достаем его специальность через твою функцию
        if doctor:
            # Ищем spec_id (или main_spec_id, если колонка еще так называется)
            spec_id = getattr(doctor, 'spec_id', None) or getattr(doctor, 'main_spec_id', None)

            if spec_id:
                # Получаем реальное название профессии (Терапевт, Хирург и т.д.)
                real_spec = await repo.get_spec_name(spec_id)
                if real_spec:
                    doc_spec = real_spec

        # Сохраняем профессию в память для отчета
        await TempDataManager.set(state, "doc_spec", doc_spec)

        # 3. Переходим к клавиатуре с препаратами
        items = await ensure_prep_items_loaded(state)
        await TempDataManager.set(state, "selected_items", [])

        kb = build_multi_select_keyboard(items, [], "doc")

        await state.set_state(PrescriptionFSM.choose_meds)
        await callback.message.edit_text(
            f"👨‍⚕️ <b>{doc_name}</b> ({doc_spec})\n💊 Выберите препараты:",
            reply_markup=kb
        )
    await callback.answer()

# ============================================================
# 9. АПТЕКА: ВВОД КОЛИЧЕСТВА (HELPER)
# ============================================================
async def ask_next_pharmacy_item(message: types.Message, state: FSMContext):
    queue = await TempDataManager.get(state, "quantity_queue", [])

    # Если очередь пуста - финиш
    if not queue:
        final_quantities = await TempDataManager.get(state, "final_quantities", {})
        prep_map = await TempDataManager.get(state, "prep_map", {})

        summary_text = "<b>✅ Данные приняты:</b>\n\n"
        for p_id_str, val in final_quantities.items():
            name = prep_map.get(str(p_id_str)) or prep_map.get(int(p_id_str)) or f"ID {p_id_str}"
            summary_text += f"• {name}\n   └ Заявка: {val['req']} | Остаток: {val['rem']}\n"

        await message.answer(summary_text)
        await message.answer("✍️ <b>Напишите комментарий</b> (или отправьте '-', если нет):")
        await state.set_state(PrescriptionFSM.pharmacy_comments)
        return

    # Берем следующий ID
    current_id = queue[0]
    prep_map = await TempDataManager.get(state, "prep_map", {})
    current_name = prep_map.get(str(current_id)) or prep_map.get(int(current_id)) or f"ID {current_id}"

    await TempDataManager.set(state, "current_process_id", current_id)
    await TempDataManager.set(state, "current_process_name", current_name)

    await message.answer(
        f"💊 Препарат: <b>{current_name}</b>\n\n"
        f"1️⃣ Введите <b>ЗАЯВКУ</b> (сколько заказать):"
    )
    await state.set_state(PrescriptionFSM.waiting_for_req_qty)


# ============================================================
# 10. ОБРАБОТЧИКИ ВВОДА (Оставляем как есть)
# ============================================================
@router.message(PrescriptionFSM.waiting_for_req_qty)
async def process_req_qty(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        return await message.answer("⚠️ Введите целое число.")

    await TempDataManager.set(state, "temp_req_qty", int(message.text))
    med_name = await TempDataManager.get(state, "current_process_name")

    await message.answer(f"✅ Заявка принята.\n2️⃣ Введите <b>ОСТАТОК</b> для {med_name}:")
    await state.set_state(PrescriptionFSM.waiting_for_rem_qty)


@router.message(PrescriptionFSM.waiting_for_rem_qty)
async def process_rem_qty(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        return await message.answer("⚠️ Введите целое число.")

    qty_rem = int(message.text)
    qty_req = await TempDataManager.get(state, "temp_req_qty")
    current_id = await TempDataManager.get(state, "current_process_id")

    final_quantities = await TempDataManager.get(state, "final_quantities", {})
    final_quantities[str(current_id)] = {"req": qty_req, "rem": qty_rem}
    await TempDataManager.set(state, "final_quantities", final_quantities)

    queue = await TempDataManager.get(state, "quantity_queue", [])
    if queue: queue.pop(0)
    await TempDataManager.set(state, "quantity_queue", queue)

    await ask_next_pharmacy_item(message, state)


@router.message(PrescriptionFSM.pharmacy_comments)
async def process_pharmacy_comment(message: types.Message, state: FSMContext):
    comment = message.text.strip()
    if comment.lower() in ["-", "нет", "no", "."]:
        comment = ""

    await TempDataManager.set(state, "comms", comment)

    # Кнопка "Загрузить / Посмотреть"
    kb = get_confirm_inline(mode=True)

    # 🔥 ВОТ ТУТ МЫ ПЕРЕХОДИМ В CONFIRMATION (И ЭТО ЛОВИТ save_handler.py)
    await state.set_state(PrescriptionFSM.confirmation)

    await message.answer("✅ Отчет готов. Сохранить?", reply_markup=kb)


@router.callback_query(F.data.startswith("docpage_"))
async def paginate_doctors(callback: types.CallbackQuery, state: FSMContext):
    try:
        parts = callback.data.split("_")
        lpu_id, page = int(parts[1]), int(parts[2])

        async for session in db_helper.get_pharmacy_session():
            repo = PharmacyRepository(session)
            doctors = await repo.get_doctors_by_lpu(lpu_id)
            kb = await get_doctors_inline(doctors, lpu_id, page, state)
            with suppress(TelegramBadRequest):
                await callback.message.edit_reply_markup(reply_markup=kb)
    except Exception:
        pass
    await callback.answer()