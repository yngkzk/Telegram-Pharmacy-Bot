from aiogram import Router, types, F
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import ReplyKeyboardRemove
from storage.temp_data import TempDataManager
from keyboard.inline import inline_buttons

from loader import pharmacyDB
from utils.logger.logger_config import logger
from states.add.prescription_state import PrescriptionFSM


router = Router()


@router.message(PrescriptionFSM.contract_terms)
async def get_and_set_ct(message: types.Message, state: FSMContext):
    """Достаем или ставим новый договор с врачей из БД"""
    text = message.text

    # Сохраняю значение во временной памяти
    await TempDataManager.set(state, key="tota", value=text)

    # Задаю новый FSM
    await state.set_state(PrescriptionFSM.comments)

    # LOG
    logger.debug(f"Current FSM - {await state.get_state()}")
    logger.info(f"Пользователь {message.from_user.first_name} договорился на {text}!")

    # Отвечаем пользователю
    await message.answer(f"✅ Ваш договор - {text}")
    await message.answer(f"✍️ Напишите ваш комментарии:")


@router.message(PrescriptionFSM.comments)
async def set_commentary(message: types.Message, state: FSMContext):
    """Добавляем комментарии"""
    text = message.text

    # Сохраняю значение во временной памяти
    await TempDataManager.set(state, key="comms", value=text)

    # Задаю новый FSM для подтверждения выбора
    await state.set_state(PrescriptionFSM.confirm)

    # LOG
    logger.debug(f"Current FSM - {await state.get_state()}")
    logger.info(f"Пользователь {message.from_user.first_name} комментировал {text}!")

    # Отвечаем пользователю
    await message.answer(f"✅ Ваш комментарии - {text}")
    await message.answer(f"📌 Хотите посмотреть или загрузить отчет?",
                         reply_markup=inline_buttons.get_confirm_inline(mode=1))
