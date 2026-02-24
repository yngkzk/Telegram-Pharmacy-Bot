from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
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

    # 🔥 Перешли на нативный FSM
    await state.update_data(contract_terms=terms_text)

    # Переходим к комментарию
    await state.set_state(PrescriptionFSM.pharmacy_comments)
    await message.answer(
        "✍️ <b>Условия приняты.</b>\nТеперь напишите комментарий к визиту (или отправьте '-' если нет):"
    )


# ============================================================
# 💊 PHARMACY FLOW: 1. Quantity (Заявка)
# ============================================================
@router.message(PrescriptionFSM.waiting_for_quantity, F.text)
async def process_quantity(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        return await message.answer("🔢 Пожалуйста, введите <b>целое число</b> (например: 10).")

    qty = int(message.text)
    await state.update_data(quantity=qty)

    await state.set_state(PrescriptionFSM.waiting_for_remaining)
    await message.answer("📦 <b>Введите остаток</b> (сколько упаковок есть сейчас):")


# ============================================================
# 💊 PHARMACY FLOW: 2. Remaining (Остатки)
# ============================================================
@router.message(PrescriptionFSM.waiting_for_remaining, F.text)
async def process_remaining(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        return await message.answer("🔢 Пожалуйста, введите <b>целое число</b>.")

    rem = int(message.text)
    await state.update_data(remaining=rem)

    await state.set_state(PrescriptionFSM.pharmacy_comments)
    await message.answer("✍️ <b>Напишите комментарий</b> (или отправьте '-', если нет):")


# ============================================================
# 💬 COMMON: Comments (Handles both Doctor & Pharmacy)
# ============================================================
@router.message(PrescriptionFSM.pharmacy_comments)
async def process_comments(message: types.Message, state: FSMContext):
    comment_text = message.text.strip()

    if comment_text.lower() in ["-", "нет", "net", ".", "no"]:
        comment_text = ""

    await state.update_data(comms=comment_text)
    await state.set_state(PrescriptionFSM.confirmation)

    # Генерируем умное превью для проверки
    data = await state.get_data()
    prefix = data.get("prefix", "doc")

    # 🔥 ИСПРАВЛЕНИЕ БАГА: Разделяем превью для врача и аптеки
    if prefix == "doc":
        doc_name = data.get("doc_name", "Врач")
        terms = data.get("contract_terms", "Нет")

        preview = (
            f"📋 <b>Проверка данных:</b>\n"
            f"👨‍⚕️ Врач: {doc_name}\n"
            f"📝 Условия: {terms}\n"
            f"💬 Комментарий: {comment_text if comment_text else '—'}\n\n"
            f"Всё верно?"
        )
    else:
        # Для аптеки имя может лежать в apt_name или lpu_name
        apt_name = data.get("apt_name") or data.get("lpu_name") or "Аптека"

        preview = (
            f"📋 <b>Проверка данных:</b>\n"
            f"🏪 Аптека: {apt_name}\n"
            f"💬 Комментарий: {comment_text if comment_text else '—'}\n\n"
            f"Всё верно?"
        )

    await message.answer(preview, reply_markup=inline_buttons.get_confirm_inline())