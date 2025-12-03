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
@router.message(PrescriptionFSM.contract_terms, F.text)
async def process_contract_terms(message: types.Message, state: FSMContext):
    text = message.text.strip()

    # Validation: Don't allow empty or too short text
    if len(text) < 2:
        await message.answer("⚠️ Текст слишком короткий. Напишите подробнее.")
        return

    await TempDataManager.set(state, key="term", value=text)

    # Next step: Comments
    await state.set_state(PrescriptionFSM.doctor_comments)

    logger.info(f"User {message.from_user.id} set terms: {text}")
    await message.answer(f"✅ Условие принято.\n\n✍️ <b>Напишите комментарий</b> (или отправьте '-', если нет):")


# ============================================================
# 💊 PHARMACY FLOW: 1. Quantity (Заявка)
# ============================================================
@router.message(PrescriptionFSM.waiting_for_quantity, F.text)
async def process_quantity(message: types.Message, state: FSMContext):
    # Validation: Must be a number
    if not message.text.isdigit():
        await message.answer("🔢 Пожалуйста, введите <b>целое число</b> (например: 10).")
        return

    qty = int(message.text)
    await TempDataManager.set(state, key="quantity", value=qty)

    # Next step: Remaining Stock
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

    # Next step: Comments
    await state.set_state(PrescriptionFSM.pharmacy_comments)
    await message.answer("✍️ <b>Напишите комментарий</b> (или отправьте '-', если нет):")


# ============================================================
# 💬 COMMON: Comments (Handles both Doctor & Pharmacy)
# ============================================================
@router.message(PrescriptionFSM.doctor_comments, F.text)
@router.message(PrescriptionFSM.pharmacy_comments, F.text)
async def process_comments(message: types.Message, state: FSMContext):
    text = message.text.strip()

    # Handle "Skip" if user sends dash
    if text in ["-", ".", "нет"]:
        text = "Без комментария"

    await TempDataManager.set(state, key="comms", value=text)

    # Move to Final Confirmation
    await state.set_state(PrescriptionFSM.confirmation)

    # --- GENERATE SUMMARY ---
    data = await TempDataManager.get_all(state)
    prefix = data.get("prefix")

    summary = "📝 <b>Проверьте данные отчёта:</b>\n\n"

    if prefix == "doc":
        summary += (
            f"👨‍⚕️ <b>Врач:</b> {data.get('doc_name')}\n"
            f"📋 <b>Условия:</b> {data.get('term')}\n"
        )
    elif prefix == "apt":
        summary += (
            f"🏥 <b>Аптека:</b> {data.get('lpu_name')}\n"
            f"🔢 <b>Заявка:</b> {data.get('quantity')}\n"
            f"📦 <b>Остаток:</b> {data.get('remaining')}\n"
        )

    summary += f"💬 <b>Комментарий:</b> {text}\n"

    await message.answer(summary)
    await message.answer(
        "📌 Всё верно? Нажмите кнопку ниже, чтобы сохранить.",
        reply_markup=inline_buttons.get_confirm_inline(mode=True)
    )