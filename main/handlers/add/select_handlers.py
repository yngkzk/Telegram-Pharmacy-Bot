from contextlib import suppress
from typing import List, Tuple

from aiogram import Router, types, F
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from storage.temp_data import TempDataManager
from keyboard.inline.inline_select import build_multi_select_keyboard, get_prep_inline
from keyboard.inline.inline_buttons import get_doctors_inline, get_confirm_inline
from loader import pharmacyDB, reportsDB
from utils.logger.logger_config import logger
from states.add.prescription_state import PrescriptionFSM

router = Router()


# ============================================================
# 📥 LOAD & CACHE DATA
# ============================================================
async def load_items(state: FSMContext) -> List[Tuple[int, str]]:
    items = await TempDataManager.get(state, "prep_items")
    if items is None:
        raw_rows = await pharmacyDB.get_prep_list()
        items = [(row["id"], row["prep"]) for row in raw_rows]
        prep_map = {item_id: name for item_id, name in items}
        await TempDataManager.set(state, "prep_items", items)
        await TempDataManager.set(state, "prep_map", prep_map)
    return items


# ============================================================
# ☑️ TOGGLE SELECTION
# ============================================================
@router.callback_query(F.data.startswith("select_"), PrescriptionFSM.choose_meds)
async def toggle_selection(callback: types.CallbackQuery, state: FSMContext):
    try:
        _, prefix, option_id = callback.data.split("_")
        option_id = int(option_id)
    except ValueError:
        await callback.answer("❌ Ошибка данных кнопки")
        return

    items = await load_items(state)
    selected = await TempDataManager.get(state, "selected_items", [])

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
# 🔄 RESET SELECTION
# ============================================================
@router.callback_query(F.data == "reset_selection", PrescriptionFSM.choose_meds)
async def reset_selection(callback: types.CallbackQuery, state: FSMContext):
    items = await load_items(state)
    prefix = await TempDataManager.get(state, "prefix", "doc")

    await TempDataManager.set(state, "selected_items", [])
    new_keyboard = build_multi_select_keyboard(items, [], prefix)

    with suppress(TelegramBadRequest):
        await callback.message.edit_reply_markup(reply_markup=new_keyboard)

    await callback.answer("🗑 Выбор сброшен")


# ============================================================
# 🏥 LPU / APOTHECARY SELECTION
# ============================================================
@router.callback_query(F.data.startswith("lpu_"), PrescriptionFSM.choose_lpu)
async def process_lpu_selection(callback: types.CallbackQuery, state: FSMContext):
    lpu_id = int(callback.data.split("_")[-1])
    lpu_name = await TempDataManager.get_button_name(state, callback.data)

    await TempDataManager.set(state, "lpu_id", lpu_id)
    await TempDataManager.set(state, "lpu_name", lpu_name)

    data = await TempDataManager.get_all(state)
    prefix = data.get("prefix")

    if not prefix:
        prefix = "doc"
        await TempDataManager.set(state, "prefix", "doc")

    # --- ВРАЧ ---
    if prefix == "doc":
        await state.set_state(PrescriptionFSM.choose_doctor)
        keyboard = await get_doctors_inline(state, lpu_id=lpu_id)
        await callback.message.edit_text(
            f"🏥 <b>{lpu_name}</b>\n👨‍⚕️ Выберите врача:",
            reply_markup=keyboard
        )

    # --- АПТЕКА ---
    elif prefix == "apt":
        await TempDataManager.set(state, "prefix", "apt")

        await state.set_state(PrescriptionFSM.choose_apothecary.state)
        await callback.message.edit_text(
            f"🏥 <b>{lpu_name}</b>\n\nЕсть ли заявка на препараты?",
            reply_markup=get_confirm_keyboard()  # Кнопки confirm_yes / confirm_no
        )

    await callback.answer()


# ============================================================
# 🆕 HELPER: LOOP THROUGH ITEMS
# ============================================================
async def ask_next_pharmacy_item(message: types.Message, state: FSMContext):
    queue = await TempDataManager.get(state, "quantity_queue", [])
    prep_map = await TempDataManager.get(state, "prep_map", {})

    # --- 🏁 ОЧЕРЕДЬ ПУСТА (Все заполнено) ---
    if not queue:
        final_quantities = await TempDataManager.get(state, "final_quantities", {})

        summary_text = "<b>✅ Данные приняты:</b>\n\n"
        for p_id, val_dict in final_quantities.items():
            name = prep_map.get(p_id, "Unknown")
            # val_dict: {'req': X, 'rem': Y}
            req = val_dict.get('req', 0)
            rem = val_dict.get('rem', 0)
            summary_text += f"• {name}\n   └ Заявка: {req} | Остаток: {rem}\n"

        # ⚠️ Я УБРАЛ ОЧИСТКУ ДАННЫХ ЗДЕСЬ, ЧТОБЫ ОНИ НЕ ТЕРЯЛИСЬ
        # (Очистка произойдет только в upload_report)

        await message.answer(summary_text)

        # Переходим к комментарию
        await state.set_state(PrescriptionFSM.pharmacy_comments)
        await state.set_state(
            PrescriptionFSM.confirmation)  # Или можно сразу к confirmation, если комментарий через message handler

        # Для надежности используем состояние комментария
        await state.set_state(PrescriptionFSM.pharmacy_comments)
        await message.answer("✍️ <b>Напишите комментарий</b> (или отправьте '-', если нет):")
        return

    # --- 🔄 СЛЕДУЮЩИЙ ---
    current_id = queue[0]
    current_name = prep_map.get(current_id, f"ID {current_id}")

    await TempDataManager.set(state, "current_process_id", current_id)
    await TempDataManager.set(state, "current_process_name", current_name)

    await message.answer(
        f"💊 Препарат: <b>{current_name}</b>\n\n"
        f"1️⃣ Введите количество для <b>Заявки</b> (сколько заказать):"
    )
    await state.set_state(PrescriptionFSM.waiting_for_req_qty)


# ============================================================
# ✍️ ОБРАБОТЧИК КОММЕНТАРИЯ (ВАЖНО ДОБАВИТЬ)
# ============================================================
@router.message(PrescriptionFSM.pharmacy_comments)
async def process_pharmacy_comment(message: types.Message, state: FSMContext):
    comment = message.text.strip()
    if comment in ["-", "нет", "No"]:
        comment = ""

    # Сохраняем комментарий
    await TempDataManager.set(state, "comms", comment)

    # Кнопка "Посмотреть" (Show Card)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔎 Посмотреть", callback_data="show_card")]
    ])

    # Переходим в состояние подтверждения
    await state.set_state(PrescriptionFSM.confirmation)

    await message.answer("✅ Данные готовы. Нажмите кнопку ниже для проверки:", reply_markup=kb)


# ============================================================
# ✅ CONFIRM SELECTION
# ============================================================
@router.callback_query(F.data == "confirm_selection", PrescriptionFSM.choose_meds)
async def confirm_selection(callback: types.CallbackQuery, state: FSMContext):
    selected_ids = await TempDataManager.get(state, "selected_items", [])
    await load_items(state)
    prep_map = await TempDataManager.get(state, "prep_map", {})

    if not selected_ids:
        await callback.answer("⚠️ Вы ничего не выбрали!", show_alert=True)
        return

    prefix = await TempDataManager.get(state, "prefix")
    logger.info(f"User {callback.from_user.id} confirmed selection: {selected_ids}")

    # --- ВРАЧ ---
    if prefix == "doc":
        selected_names = [prep_map.get(i, f"ID {i}") for i in selected_ids]
        formatted_list = "\n".join(f"• {name}" for name in selected_names)
        response_text = f"✅ <b>Список сохранён:</b>\n{formatted_list}\n\n"
        response_text += "✍️ <b>Введите условия договора</b> (например: 10% скидка):"
        await callback.message.edit_text(response_text)
        await state.set_state(PrescriptionFSM.contract_terms)
        # Для врача можно очистить карту, данные уже в тексте/списке
        await TempDataManager.remove(state, "prep_items", "prep_map")

    # --- АПТЕКА ---
    elif prefix == "apt":
        await TempDataManager.set(state, "quantity_queue", list(selected_ids))
        await TempDataManager.set(state, "final_quantities", {})

        # Подстраховка: еще раз явно сохраним prefix apt
        await TempDataManager.set(state, "prefix", "apt")

        await callback.message.edit_text("✅ <b>Список принят.</b>\nПереходим к вводу количества.")
        await ask_next_pharmacy_item(callback.message, state)

    else:
        await callback.answer("⚠️ Ошибка состояния", show_alert=True)


# ============================================================
# 🔢 PHARMACY STEP 1: REQUEST
# ============================================================
@router.message(PrescriptionFSM.waiting_for_req_qty)
async def process_req_qty(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("⚠️ Пожалуйста, введите целое число для заявки.")
        return

    qty_req = int(message.text)
    await TempDataManager.set(state, "temp_req_qty", qty_req)

    med_name = await TempDataManager.get(state, "current_process_name")
    await message.answer(
        f"✅ Заявка: {qty_req}\n\n"
        f"2️⃣ Теперь введите <b>Остаток</b> (для {med_name}):"
    )
    await state.set_state(PrescriptionFSM.waiting_for_rem_qty)


# ============================================================
# 📦 PHARMACY STEP 2: REMAINING
# ============================================================
@router.message(PrescriptionFSM.waiting_for_rem_qty)
async def process_rem_qty(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("⚠️ Пожалуйста, введите целое число.")
        return

    qty_rem = int(message.text)
    qty_req = await TempDataManager.get(state, "temp_req_qty")
    current_id = await TempDataManager.get(state, "current_process_id")

    # Словарь
    value_data = {
        "req": qty_req,
        "rem": qty_rem
    }

    final_quantities = await TempDataManager.get(state, "final_quantities", {})
    final_quantities[current_id] = value_data
    await TempDataManager.set(state, "final_quantities", final_quantities)

    queue = await TempDataManager.get(state, "quantity_queue", [])
    if queue:
        queue.pop(0)
    await TempDataManager.set(state, "quantity_queue", queue)

    await ask_next_pharmacy_item(message, state)


# ============================================================
# 📄 PAGINATION
# ============================================================
@router.callback_query(F.data.startswith("docpage_"))
async def paginate_doctors(callback: types.CallbackQuery, state: FSMContext):
    try:
        parts = callback.data.split("_")
        lpu_id = int(parts[1])
        page = int(parts[2])

        keyboard = await get_doctors_inline(state, lpu_id=lpu_id, page=page)
        try:
            await callback.message.edit_reply_markup(reply_markup=keyboard)
        except Exception:
            pass
    except Exception as e:
        logger.error(f"Pagination error: {e}")
    await callback.answer()


# ============================================================
# 👨‍⚕️ DOCTOR SELECTION
# ============================================================
@router.callback_query(F.data.startswith("doc_"), PrescriptionFSM.choose_doctor)
async def process_doctor(callback: types.CallbackQuery, state: FSMContext):
    doc_id = int(callback.data.split("_")[-1])
    doc_name = await pharmacyDB.get_doctor_name(doc_id)
    user_name = callback.from_user.full_name

    await TempDataManager.set(state, "doc_id", doc_id)
    await TempDataManager.set(state, "doc_name", doc_name)

    row = await pharmacyDB.get_doc_stats(doc_id)
    if row:
        await TempDataManager.set(state, "doc_spec", row["spec"])
        await TempDataManager.set(state, "doc_num", row["numb"])
    else:
        await TempDataManager.set(state, "doc_spec", "Не указано")
        await TempDataManager.set(state, "doc_num", None)

    last_report = await reportsDB.get_last_doctor_report(user_name, doc_name)

    report_text = ""
    if last_report:
        preps_str = "\n".join([f"• {p}" for p in last_report['preps']]) if last_report['preps'] else "—"
        report_text = (
            f"📅 <b>Предыдущий отчёт ({last_report['date']}):</b>\n"
            f"📝 <b>Условия:</b> {last_report['term']}\n"
            f"💊 <b>Препараты:</b>\n{preps_str}\n"
            f"💬 <b>Комментарий:</b> {last_report['commentary']}\n"
            f"➖➖➖➖➖➖➖➖➖➖\n\n"
        )

    await state.set_state(PrescriptionFSM.choose_meds)
    await TempDataManager.set(state, "prefix", "doc")
    await TempDataManager.set(state, "selected_items", [])

    keyboard = await get_prep_inline(state, prefix="doc")

    await callback.message.edit_text(
        f"{report_text}👨‍⚕️ <b>{doc_name}</b>\n💊 Выберите препараты:",
        reply_markup=keyboard
    )
    await callback.answer()