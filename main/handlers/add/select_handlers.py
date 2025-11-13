from aiogram import Router, types, F
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import ReplyKeyboardRemove
from storage.temp_data import TempDataManager
from keyboard.inline_select import build_multi_select_keyboard
from loader import pharmacyDB
from utils.logger_config import logger
from states.prescription_state import PrescriptionFSM


router = Router()

# Загружаем список препаратов: [(id, name), ...]
items = pharmacyDB.get_prep_list()


@router.callback_query(F.data.startswith("select_"), PrescriptionFSM.choose_meds)
async def toggle_selection(callback: types.CallbackQuery, state: FSMContext):
    """Добавляем или убираем выбранный пункт"""
    option_id = int(callback.data.replace("select_", ""))
    selected = await TempDataManager.get(state, "selected_items", [])

    # LOG
    logger.debug(f"Current FSM - {await state.get_state()}")

    # --- сохраняем словарь ID → имя препарата (1 раз при первом вызове)
    prep_map = {i: name for i, name in items}
    await TempDataManager.set(state, "prep_map", prep_map)

    # --- переключаем выбор
    if option_id in selected:
        selected.remove(option_id)
    else:
        selected.append(option_id)

    await TempDataManager.set(state, "selected_items", selected)

    new_keyboard = build_multi_select_keyboard(items, selected)
    try:
        await callback.message.edit_reply_markup(reply_markup=new_keyboard)
    except TelegramBadRequest:
        pass

    await callback.answer()


@router.callback_query(F.data == "reset_selection")
async def reset_selection(callback: types.CallbackQuery, state: FSMContext):
    await TempDataManager.set(state, "selected_items", [])
    new_keyboard = build_multi_select_keyboard(items, [])
    try:
        await callback.message.edit_reply_markup(reply_markup=new_keyboard)
    except TelegramBadRequest:
        pass
    await callback.answer("Выбор сброшен ✅")


@router.callback_query(F.data == "confirm_selection")
async def confirm_selection(callback: types.CallbackQuery, state: FSMContext):
    """Подтверждение выбора"""
    selected = await TempDataManager.get(state, "selected_items", [])
    prep_map = await TempDataManager.get(state, "prep_map", {})

    if not selected:
        await callback.answer("⚠️ Ничего не выбрано", show_alert=True)
        return

    # --- преобразуем ID → имена
    selected_names = [prep_map.get(i, f"#{i}") for i in selected]

    # LOG
    logger.debug(f"Current FSM - {await state.get_state()}")
    logger.info(f"Пользователь {callback.from_user.first_name} выбрал препараты {selected_names}")

    # Задаю новый FSM
    await state.set_state(PrescriptionFSM.contract_terms)

    text = "📋 Вы выбрали препараты:\n" + "\n".join(f"• {name}" for name in selected_names)
    await callback.message.answer(text=text)
    await callback.message.edit_text(text="✍️ Введите условие договора")

    await TempDataManager.remove(state, "selected_items", "prep_map")
    await callback.answer("✅ Выбор сохранён")