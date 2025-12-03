from aiogram import Router, types, F
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from storage.temp_data import TempDataManager
from keyboard.inline.inline_select import build_multi_select_keyboard
from loader import pharmacyDB
from utils.logger.logger_config import logger
from states.add.prescription_state import PrescriptionFSM


router = Router()


# === Загружаем список препаратов перед первым использованием ===
async def load_items(state: FSMContext):
    """
    Загружает список препаратов в FSM, если их там ещё нет.
    Это заменяет глобальный вызов pharmacyDB.get_prep_list().
    """
    items = await TempDataManager.get(state, "prep_items")
    if items is None:
        items = await pharmacyDB.get_prep_list()  # <-- async!
        await TempDataManager.set(state, "prep_items", items)
    return items


# === Выбор препарата (multi-select) ===
@router.callback_query(F.data.startswith("select_"), PrescriptionFSM.choose_meds)
async def toggle_selection(callback: types.CallbackQuery, state: FSMContext):
    prefix, select, option_id = callback.data.split("_")

    option_id = int(option_id)

    items = await load_items(state)
    selected = await TempDataManager.get(state, "selected_items", [])

    # LOG
    logger.info(f"TOGGLE_SELECTION: {prefix}_{select}_{option_id}")
    logger.debug(f"Current FSM - {await state.get_state()}")

    # — Препараты: создаём карту id → имя
    prep_map = {i: name for i, name in items}
    await TempDataManager.set(state, "prep_map", prep_map)

    # — Переключение выбора
    if option_id in selected:
        selected.remove(option_id)
    else:
        selected.append(option_id)

    await TempDataManager.set(state, "selected_items", selected)

    new_keyboard = build_multi_select_keyboard(items, selected, prefix)

    try:
        await callback.message.edit_reply_markup(reply_markup=new_keyboard)
    except TelegramBadRequest:
        pass

    await callback.answer()


# === Сброс выбора ===
@router.callback_query(F.data == "reset_selection", PrescriptionFSM.choose_meds)
async def reset_selection(callback: types.CallbackQuery, state: FSMContext):
    items = await load_items(state)

    await TempDataManager.set(state, "selected_items", [])

    new_keyboard = build_multi_select_keyboard(items, [])

    try:
        await callback.message.edit_reply_markup(reply_markup=new_keyboard)
    except TelegramBadRequest:
        pass

    await callback.answer("Выбор сброшен ✅")


# === Подтверждение выбора ===
@router.callback_query(F.data == "confirm_selection", PrescriptionFSM.choose_meds)
async def confirm_selection(callback: types.CallbackQuery, state: FSMContext):
    selected = await TempDataManager.get(state, "selected_items", [])
    prep_map = await TempDataManager.get(state, "prep_map", {})

    if not selected:
        await callback.answer("⚠️ Ничего не выбрано", show_alert=True)
        return

    selected_names = [prep_map.get(i, f"#{i}") for i in selected]

    # LOG
    logger.debug(f"Current FSM - {await state.get_state()}")
    logger.info(f"Пользователь {callback.from_user.first_name} выбрал препараты {selected_names}")

    prefix = await TempDataManager.get(state, "prefix")

    if prefix == "doc":
        await state.set_state(PrescriptionFSM.contract_terms)
        await callback.message.edit_text("✍️ Введите условие договора")
    elif prefix == "apt":

        await callback.message.edit_text("✍️ На какое количество препаратов заявка")


    # Отвечаем пользователю
    await callback.message.answer(
        "📋 Вы выбрали препараты:\n" + "\n".join(f"• {name}" for name in selected_names)
    )
    await callback.answer("✅ Выбор сохранён")

    # Очищаем временные данные
    await TempDataManager.remove(state, "selected_items", "prep_map", "prep_items")
