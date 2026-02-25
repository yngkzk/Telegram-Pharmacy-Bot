from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext

# DI Репозитории
from infrastructure.database.repo.pharmacy_repo import PharmacyRepository

# Состояния
from states.add.prescription_state import PrescriptionFSM
from states.add.add_state import AddDoctor
from utils.ui.ui_helper import safe_clear_state

# Клавиатуры
from keyboard.inline import inline_buttons


router = Router()


# ============================================================
# ✅ ОБЩИЕ ПОДТВЕРЖДЕНИЯ (Да / Нет)
# ============================================================

@router.callback_query(F.data.in_(["confirm_yes", "confirm_no"]))
async def handle_confirmation(
        callback: types.CallbackQuery,
        state: FSMContext,
        pharmacy_repo: PharmacyRepository
):
    is_yes = (callback.data == "confirm_yes")
    current_state = await state.get_state()

    if current_state == PrescriptionFSM.confirmation.state:
        # Если нужно что-то делать на этапе финального подтверждения — пишем здесь
        return

    # --------------------------------------------------------
    # ВЕТКА 1: Подтверждение заявки в аптеке
    # --------------------------------------------------------
    if current_state == PrescriptionFSM.choose_apothecary.state:
        await state.update_data(prefix="apt")

        if is_yes:
            await state.set_state(PrescriptionFSM.choose_meds)

            # Используем DI (никаких async for session!)
            preps = await pharmacy_repo.get_preps()
            keyboard = await inline_buttons.build_keyboard_from_items(
                preps, prefix="apt", state=state, row_width=2
            )

            await callback.message.edit_text(
                "💊 Выберите препараты из списка:",
                reply_markup=keyboard
            )
        else:
            # Массовое обновление стейта (быстрее и чище)
            await state.update_data(
                quantity=0,
                remaining=0,
                selected_items=[]
            )

            await state.set_state(PrescriptionFSM.pharmacy_comments)
            await callback.message.edit_text("👌 Хорошо, визит без заявки.")
            await callback.message.answer("✍️ Напишите комментарий к визиту:")

        await callback.answer()
        return

    # --------------------------------------------------------
    # ВЕТКА 2: Подтверждение добавления врача
    # --------------------------------------------------------
    if current_state == AddDoctor.waiting_for_confirmation.state:
        if is_yes:
            await callback.message.edit_text("✅ Врач успешно добавлен!")
        else:
            await callback.message.edit_text("❌ Добавление отменено.")

        await safe_clear_state(state)
        await callback.answer()
        return

    await callback.answer()