from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from storage.temp_data import TempDataManager
from keyboard.inline import inline_buttons

from utils.logger.logger_config import logger
from states.add.prescription_state import PrescriptionFSM

router = Router()


# ============================================================
# 👨‍⚕️ DOCTOR FLOW: 1. Contract Terms
# ============================================================
@router.message(PrescriptionFSM.contract_terms)
async def process_contract_terms(message: types.Message, state: FSMContext):
    terms_text = message.text.strip()

    # 🔥 ИСПРАВЛЕНИЕ 2: Сохраняем в правильный ключ "contract_terms"
    await TempDataManager.set(state, "contract_terms", terms_text)

    # Переходим к комментарию
    await state.set_state(PrescriptionFSM.pharmacy_comments)  # Используем одно состояние для комментов
    await message.answer(
        "✍️ <b>Условия приняты.</b>\nТеперь напишите комментарий к визиту (или отправьте '-' если нет):")


# ============================================================
# 💊 PHARMACY FLOW: 1. Quantity (Заявка)
# ============================================================
@router.message(PrescriptionFSM.waiting_for_quantity, F.text)
async def process_quantity(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("🔢 Пожалуйста, введите <b>целое число</b> (например: 10).")
        return

    qty = int(message.text)
    await TempDataManager.set(state, key="quantity", value=qty)
    await state.set_state(PrescriptionFSM.waiting_for_remaining)
    await message.answer("📦 <b>Введите остаток</b> (сколько упаковок есть сейчас):")


# ============================================================
# 💊 PHARMACY FLOW: 2. Remaining (Остатки)
# ============================================================
@router.message(PrescriptionFSM.waiting_for_remaining, F.text)
async def process_remaining(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("🔢 Пожалуйста, введите <b>целое число</b>.")
        return

    rem = int(message.text)
    await TempDataManager.set(state, key="remaining", value=rem)
    await state.set_state(PrescriptionFSM.pharmacy_comments)
    await message.answer("✍️ <b>Напишите комментарий</b> (или отправьте '-', если нет):")


# ============================================================
# 💬 COMMON: Comments (Handles both Doctor & Pharmacy)
# ============================================================
@router.message(PrescriptionFSM.pharmacy_comments)
async def process_comments(message: types.Message, state: FSMContext):
    comment_text = message.text.strip()

    if comment_text in ["-", "нет", "net", "."]:
        comment_text = ""

    await TempDataManager.set(state, "comms", comment_text)

    # Показываем кнопку подтверждения
    await state.set_state(PrescriptionFSM.confirmation)

    # Генерируем красивое превью для проверки
    data = await TempDataManager.get_all(state)
    doc_name = data.get("doc_name", "Врач")
    terms = data.get("contract_terms", "Нет")  # Проверяем, что тут сохранилось

    await message.answer(
        f"📋 <b>Проверка данных:</b>\n"
        f"👨‍⚕️ Врач: {doc_name}\n"
        f"📝 Условия: {terms}\n"
        f"💬 Комментарий: {comment_text}\n\n"
        f"Всё верно?",
        reply_markup=inline_buttons.get_confirm_inline()
    )