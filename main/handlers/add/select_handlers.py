from contextlib import suppress
from aiogram import Router, types, F
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext

from infrastructure.database.repo.pharmacy_repo import PharmacyRepository
from states.add.prescription_state import PrescriptionFSM

from keyboard.inline.inline_select import build_multi_select_keyboard
from keyboard.inline.inline_buttons import get_confirm_inline, get_doctors_inline

router = Router()


# ============================================================
# 📥 ВСПОМОГАТЕЛЬНАЯ ФУНКЦИЯ
# ============================================================
async def ensure_prep_items_loaded(state: FSMContext, pharmacy_repo: PharmacyRepository):
    data = await state.get_data()
    items = data.get("prep_items")

    if items is None:
        all_preps = await pharmacy_repo.get_preps()
        items = []
        prep_map = {}

        for p in all_preps:
            p_id = getattr(p, 'id', None)
            p_name = getattr(p, 'prep', None)

            if p_id and p_name:
                items.append((p_id, p_name))
                prep_map[str(p_id)] = p_name
                prep_map[int(p_id)] = p_name

        await state.update_data(prep_items=items, prep_map=prep_map)
    return items


# ============================================================
# 🏪 АПТЕКА: ВОПРОС "ЕСТЬ ЗАЯВКА?" -> ОТВЕТ
# ============================================================
@router.callback_query(F.data.in_(["confirm_yes", "confirm_no"]), PrescriptionFSM.choose_apothecary)
async def process_confirmation_step(
        callback: types.CallbackQuery,
        state: FSMContext,
        pharmacy_repo: PharmacyRepository
):
    if callback.data == "confirm_no":
        await state.set_state(PrescriptionFSM.pharmacy_comments)
        await callback.message.edit_text("✍️ Напишите комментарий к визиту (или «-»):")
        return await callback.answer()

    items = await ensure_prep_items_loaded(state, pharmacy_repo)
    await state.update_data(selected_items=[])

    kb = build_multi_select_keyboard(items, [], "apt")
    await state.set_state(PrescriptionFSM.choose_meds)

    await callback.message.edit_text("💊 <b>Выберите препараты:</b>", reply_markup=kb)
    await callback.answer()


# ============================================================
# ☑️ МАГИЯ ГАЛОЧЕК (Мульти-выбор)
# ============================================================
@router.callback_query(F.data.startswith("select_"), PrescriptionFSM.choose_meds)
async def toggle_selection(
        callback: types.CallbackQuery,
        state: FSMContext,
        pharmacy_repo: PharmacyRepository
):
    try:
        _, prefix, option_id = callback.data.split("_")
        option_id = int(option_id)
    except ValueError:
        return await callback.answer("Ошибка кнопки")

    data = await state.get_data()
    items = data.get("prep_items") or await ensure_prep_items_loaded(state, pharmacy_repo)
    selected = data.get("selected_items", [])

    if option_id in selected:
        selected.remove(option_id)
    else:
        selected.append(option_id)

    await state.update_data(selected_items=selected)
    new_keyboard = build_multi_select_keyboard(items, selected, prefix)

    with suppress(TelegramBadRequest):
        await callback.message.edit_reply_markup(reply_markup=new_keyboard)
    await callback.answer()


# ============================================================
# 🔄 СБРОС И ПОДТВЕРЖДЕНИЕ ВЫБОРА
# ============================================================
@router.callback_query(F.data == "reset_selection", PrescriptionFSM.choose_meds)
async def reset_selection(callback: types.CallbackQuery, state: FSMContext, pharmacy_repo: PharmacyRepository):
    items = await ensure_prep_items_loaded(state, pharmacy_repo)
    data = await state.get_data()
    prefix = data.get("prefix", "doc")

    await state.update_data(selected_items=[])
    kb = build_multi_select_keyboard(items, [], prefix)

    with suppress(TelegramBadRequest):
        await callback.message.edit_reply_markup(reply_markup=kb)
    await callback.answer("🗑 Сброшено")


@router.callback_query(F.data == "confirm_selection", PrescriptionFSM.choose_meds)
async def confirm_selection(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    selected_ids = data.get("selected_items", [])

    if not selected_ids:
        return await callback.answer("⚠️ Выберите хотя бы один препарат!", show_alert=True)

    prefix = data.get("prefix")

    if prefix == "doc":
        await state.set_state(PrescriptionFSM.contract_terms)
        prep_map = data.get("prep_map", {})
        names = [prep_map.get(str(i)) or prep_map.get(int(i)) or f"ID {i}" for i in selected_ids]
        names_str = "\n".join([f"• {n}" for n in names])

        await callback.message.edit_text(f"✅ <b>Выбрано:</b>\n{names_str}\n\n✍️ Введите условия договора:")
    elif prefix == "apt":
        await state.update_data(quantity_queue=list(selected_ids), final_quantities={})
        await callback.message.edit_text("✅ <b>Список принят.</b>\nПереходим к вводу количества.")
        await ask_next_pharmacy_item(callback.message, state)

    await callback.answer()


# ============================================================
# 🔢 АПТЕКА: ЦИКЛ ВВОДА КОЛИЧЕСТВА (FSM)
# ============================================================
async def ask_next_pharmacy_item(message: types.Message, state: FSMContext):
    data = await state.get_data()
    queue = data.get("quantity_queue", [])

    if not queue:
        final_quantities = data.get("final_quantities", {})
        prep_map = data.get("prep_map", {})

        summary_text = "<b>✅ Данные приняты:</b>\n\n"
        for p_id_str, val in final_quantities.items():
            name = prep_map.get(str(p_id_str)) or prep_map.get(int(p_id_str)) or f"ID {p_id_str}"
            summary_text += f"• {name}\n   └ Заявка: {val['req']} | Остаток: {val['rem']}\n"

        await message.answer(summary_text)
        await message.answer("✍️ <b>Напишите комментарий</b> (или отправьте '-', если нет):")
        await state.set_state(PrescriptionFSM.pharmacy_comments)
        return

    current_id = queue[0]
    prep_map = data.get("prep_map", {})
    current_name = prep_map.get(str(current_id)) or prep_map.get(int(current_id)) or f"ID {current_id}"

    await state.update_data(current_process_id=current_id, current_process_name=current_name)
    await message.answer(f"💊 Препарат: <b>{current_name}</b>\n\n1️⃣ Введите <b>ЗАЯВКУ</b> (сколько заказать):")
    await state.set_state(PrescriptionFSM.waiting_for_req_qty)


@router.message(PrescriptionFSM.waiting_for_req_qty)
async def process_req_qty(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        return await message.answer("⚠️ Введите целое число.")

    await state.update_data(temp_req_qty=int(message.text))
    data = await state.get_data()

    await message.answer(f"✅ Заявка принята.\n2️⃣ Введите <b>ОСТАТОК</b> для {data.get('current_process_name')}:")
    await state.set_state(PrescriptionFSM.waiting_for_rem_qty)


@router.message(PrescriptionFSM.waiting_for_rem_qty)
async def process_rem_qty(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        return await message.answer("⚠️ Введите целое число.")

    data = await state.get_data()
    final_quantities = data.get("final_quantities", {})
    queue = data.get("quantity_queue", [])

    final_quantities[str(data.get("current_process_id"))] = {"req": data.get("temp_req_qty"), "rem": int(message.text)}
    if queue: queue.pop(0)

    await state.update_data(final_quantities=final_quantities, quantity_queue=queue)
    await ask_next_pharmacy_item(message, state)

# Пагинация врачей (оставили тут, чтобы не потерять)
@router.callback_query(F.data.startswith("docpage_"))
async def paginate_doctors(callback: types.CallbackQuery, state: FSMContext, pharmacy_repo: PharmacyRepository):
    try:
        parts = callback.data.split("_")
        lpu_id, page = int(parts[1]), int(parts[2])
        doctors = await pharmacy_repo.get_doctors_by_lpu(lpu_id)
        kb = await get_doctors_inline(doctors, lpu_id, page, state)
        with suppress(TelegramBadRequest):
            await callback.message.edit_reply_markup(reply_markup=kb)
    except Exception:
        pass
    await callback.answer()