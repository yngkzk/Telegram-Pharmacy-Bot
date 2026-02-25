from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from keyboard.inline import inline_buttons

from states.add.prescription_state import PrescriptionFSM

router = Router()


# ============================================================
# 👨‍⚕️ ВРАЧ: Условия договора
# ============================================================
@router.message(PrescriptionFSM.contract_terms)
async def process_contract_terms(message: types.Message, state: FSMContext):
    terms_text = message.text.strip()

    await state.update_data(contract_terms=terms_text)
    await state.set_state(PrescriptionFSM.pharmacy_comments)

    await message.answer(
        "✍️ <b>Условия приняты.</b>\nТеперь напишите комментарий к визиту (или отправьте '-' если нет):"
    )


# ============================================================
# 💬 ОБЩЕЕ: Комментарии (Врач и Аптека)
# ============================================================
@router.message(PrescriptionFSM.pharmacy_comments)
async def process_comments(message: types.Message, state: FSMContext):
    comment_text = message.text.strip()

    if comment_text.lower() in ["-", "нет", "net", ".", "no"]:
        comment_text = ""

    await state.update_data(comms=comment_text)
    await state.set_state(PrescriptionFSM.confirmation)

    # Вызываем клавиатуру с кнопками "📖 Посмотреть" и "🚀 Загрузить"
    kb = inline_buttons.get_confirm_inline(mode=True)
    await message.answer("✅ <b>Данные собраны.</b> Что делаем дальше?", reply_markup=kb)


# ============================================================
# 📖 ПРОСМОТР ОТЧЕТА (Кнопка "Показать")
# ============================================================
@router.callback_query(F.data == "show_card", PrescriptionFSM.confirmation)
async def show_report_card(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    prefix = data.get("prefix", "doc")

    district = data.get("district_name", "—")
    road = data.get("road_num", "—")
    comms = data.get("comms", "—")
    if not comms:
        comms = "—"

    if prefix == "doc":
        doc_name = data.get("doc_name", "—")
        doc_spec = data.get("doc_spec", "—")
        lpu_name = data.get("lpu_name", "—")
        terms = data.get("contract_terms", "—")

        # Собираем препараты
        selected_ids = data.get("selected_items", [])
        prep_map = data.get("prep_map", {})
        preps = [prep_map.get(str(i)) or prep_map.get(int(i)) or f"ID {i}" for i in selected_ids]
        preps_str = "\n".join([f"• {p}" for p in preps]) if preps else "—"

        text = (
            f"📋 <b>ПРЕДВАРИТЕЛЬНЫЙ ПРОСМОТР</b>\n\n"
            f"📍 <b>Локация:</b> {district} (Маршрут {road})\n"
            f"🏥 <b>ЛПУ:</b> {lpu_name}\n"
            f"👨‍⚕️ <b>Врач:</b> {doc_name} ({doc_spec})\n"
            f"📝 <b>Условия:</b> {terms}\n\n"
            f"💊 <b>Препараты:</b>\n{preps_str}\n\n"
            f"💬 <b>Комментарий:</b> {comms}"
        )
    else:
        apt_name = data.get("apt_name") or data.get("lpu_name") or "—"

        # Собираем препараты с заявками и остатками
        final_quantities = data.get("final_quantities", {})
        prep_map = data.get("prep_map", {})
        preps_str = ""

        for p_id_str, vals in final_quantities.items():
            name = prep_map.get(str(p_id_str)) or prep_map.get(int(p_id_str)) or f"ID {p_id_str}"
            preps_str += f"• {name}\n   └ Заявка: {vals['req']} | Остаток: {vals['rem']}\n"

        if not preps_str:
            preps_str = "—"

        text = (
            f"📋 <b>ПРЕДВАРИТЕЛЬНЫЙ ПРОСМОТР</b>\n\n"
            f"📍 <b>Локация:</b> {district} (Маршрут {road})\n"
            f"🏪 <b>Аптека:</b> {apt_name}\n\n"
            f"💊 <b>Препараты:</b>\n{preps_str}\n"
            f"💬 <b>Комментарий:</b> {comms}"
        )

    # Обновляем сообщение, оставляя те же кнопки
    await callback.message.edit_text(
        text,
        reply_markup=inline_buttons.get_confirm_inline(mode=True)
    )
    await callback.answer()