from aiogram import Router, types
from aiogram.fsm.context import FSMContext
from storage.temp_data import TempDataManager
from keyboard.inline import inline_buttons

from utils.logger.logger_config import logger
from states.add.prescription_state import PrescriptionFSM


router = Router()


# === 1️⃣ Получение условий договора ===
@router.message(PrescriptionFSM.contract_terms)
async def get_and_set_ct(message: types.Message, state: FSMContext):
    """Сохраняет условие договора (term)"""
    text = message.text.strip()

    await TempDataManager.set(state, key="term", value=text)

    await state.set_state(PrescriptionFSM.comments)

    logger.debug(f"FSM -> {await state.get_state()}")
    logger.info(f"Пользователь {message.from_user.first_name} указал условие: {text}")

    await message.answer(f"✅ Условие договора сохранено:\n{text}")
    await message.answer("✍️ Напишите ваш комментарий:")


# === 2️⃣ Получение комментария ===
@router.message(PrescriptionFSM.comments)
async def set_commentary(message: types.Message, state: FSMContext):
    """Сохраняет комментарий перед подтверждением"""
    text = message.text.strip()

    await TempDataManager.set(state, key="comms", value=text)

    await state.set_state(PrescriptionFSM.confirm)

    logger.debug(f"FSM -> {await state.get_state()}")
    logger.info(f"Пользователь {message.from_user.first_name} оставил комментарий: {text}")

    await message.answer(f"💬 Комментарий сохранён:\n{text}")
    await message.answer(
        "📌 Хотите посмотреть или загрузить отчет?",
        reply_markup=inline_buttons.get_confirm_inline(mode=True)
    )
