from aiogram import Router, types, F
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import ReplyKeyboardRemove, CallbackQuery

from storage.temp_data import TempDataManager
from keyboard.inline import inline_buttons

from loader import pharmacyDB
from utils.logger.logger_config import logger
from states.add.prescription_state import PrescriptionFSM


router = Router()


@router.callback_query(F.data == "show_card", PrescriptionFSM.confirm)
async def show_card(callback: CallbackQuery, state: FSMContext):
    # LOG
    logger.info(f"Пользователь {callback.from_user.first_name} дошел до {await state.get_state()}")

    # Берем данные из БД
    district, road, lpu, lpu_id = await TempDataManager.get_many(state, "district", "road", "lpu_name", "lpu_id")
    doctor_name, doctor_spec, doctor_number = await TempDataManager.get_many(state, "tp_dr_name", "tp_dr_spec", "tp_dr_phone")
    term, commas = await TempDataManager.get_many(state, "tota", "comms")
    selected = await TempDataManager.get(state, "selected_items", [])
    prep_map = await TempDataManager.get(state, "prep_map", {})

    # Преобразуем ID -> Имена препаратов
    selected_names = [prep_map.get(i, f"#{i}") for i in selected]
    selected_text = "\n".join([f"• {name}" for name in selected_names])

    text = (
        f"\n\n🏥 Назначает препараты:\n"
        f"{selected_text}"
    )


    # Отвечаем пользователю
    await callback.message.answer(f"Ваш запрос:"
                         f"\nРайон - {district}"
                         f"\n🗺 Маршрут № - {road}"
                         f"\n📍 ЛПУ - {lpu}"
                         f"\n🥼 Врач - {doctor_name}"
                         f"\n(Специальность - {doctor_spec})"
                         f"{text}"
                         f"\n\n✍️ Договор: {term}"
                         f"\n✍️ Комментарии: {commas}")
    await callback.answer()


@router.callback_query(F.data == "mp_up", PrescriptionFSM.confirm)
async def upload_report(callback: CallbackQuery, state: FSMContext):
    # LOG
    logger.info(f"Пользователь {callback.from_user.first_name} дошел до {await state.get_state()}")
