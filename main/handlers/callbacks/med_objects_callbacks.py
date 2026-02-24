from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext

# 🔥 НОВЫЕ ИМПОРТЫ РЕПОЗИТОРИЕВ
from infrastructure.database.repo.pharmacy_repo import PharmacyRepository
from infrastructure.database.repo.report_repo import ReportRepository

# Состояния и клавиатуры
from states.add.prescription_state import PrescriptionFSM
from keyboard.inline import inline_buttons

router = Router()


# ============================================================
# 🏥 ЛПУ и ВРАЧИ (Выбор из списка)
# ============================================================

@router.callback_query(F.data.startswith("lpu_"), PrescriptionFSM.choose_lpu)
async def process_lpu(
        callback: types.CallbackQuery,
        state: FSMContext,
        pharmacy_repo: PharmacyRepository
):
    lpu_id = int(callback.data.split("_")[-1])

    # 1. Забираем эталонные данные из базы, а не с кнопок!
    lpu = await pharmacy_repo.get_lpu_by_id(lpu_id)
    if not lpu:
        return await callback.answer("❌ ЛПУ не найдено в базе", show_alert=True)

    # 2. Сохраняем все данные в нативный FSM за один раз
    await state.update_data(
        lpu_id=lpu_id,
        lpu_name=lpu.name
    )

    await state.set_state(PrescriptionFSM.choose_doctor)

    url_info = f"\n🔗 <a href='{lpu.url}'>Открыть в 2GIS</a>" if lpu.url else ""

    # Загружаем врачей
    doctors = await pharmacy_repo.get_doctors_by_lpu(lpu_id)
    keyboard = await inline_buttons.get_doctors_inline(doctors, lpu_id=lpu_id, page=1, state=state)

    await callback.message.edit_text(
        f"🏥 <b>{lpu.name}</b>{url_info}\n\n👨‍⚕️ Выберите врача:",
        reply_markup=keyboard,
        disable_web_page_preview=True
    )
    await callback.answer()


@router.callback_query(F.data.startswith("doc_"), PrescriptionFSM.choose_doctor)
async def process_doctor(
        callback: types.CallbackQuery,
        state: FSMContext,
        pharmacy_repo: PharmacyRepository,
        reports_db: ReportRepository
):
    doc_id = int(callback.data.split("_")[-1])
    user_name = callback.from_user.full_name

    doctor = await pharmacy_repo.get_doctor_by_id(doc_id)
    if not doctor:
        return await callback.answer("❌ Врач не найден", show_alert=True)

    # Чистое получение специальности (без getattr хаков)
    # Если в модели ORM есть relationship, это будет просто doctor.specialty.name
    # Пока оставляем фоллбэк на безопасный вызов
    actual_spec_id = getattr(doctor, 'spec_id', getattr(doctor, 'main_spec_id', None))
    spec_name = "Не указана"

    if actual_spec_id:
        fetched_spec = await pharmacy_repo.get_spec_name(actual_spec_id)
        if fetched_spec:
            spec_name = fetched_spec

    # Массовое обновление стейта
    await state.update_data(
        doc_id=doc_id,
        doc_name=doctor.doctor,
        doc_spec=spec_name,
        doc_num=doctor.numb,
        prefix="doc",
        selected_items=[]
    )

    # Загружаем препараты
    preps = await pharmacy_repo.get_preps()
    keyboard = await inline_buttons.build_keyboard_from_items(
        preps, prefix="doc", state=state, row_width=2, add_new_btn_callback="add_prep"
    )

    # Legacy: Статистика из старых отчетов
    last_report = await reports_db.get_last_doctor_report(user_name, doctor.doctor)
    report_text = ""
    if last_report:
        preps_str = "\n".join([f"• {p}" for p in last_report['preps']]) if last_report['preps'] else "—"
        report_text = (
            f"📅 <b>Предыдущий отчёт ({last_report['date']}):</b>\n"
            f"📝 <b>Условия:</b> {last_report['term']}\n"
            f"💊 <b>Препараты:</b>\n{preps_str}\n"
            f"💬 <b>Комментарий:</b> {last_report['commentary']}\n"
            f"➖➖➖➖➖➖➖➖➖➖\n\n"
        )

    await state.set_state(PrescriptionFSM.choose_meds)

    await callback.message.edit_text(
        f"{report_text}👨‍⚕️ <b>{doctor.doctor}</b>\n💊 Выберите препараты:",
        reply_markup=keyboard
    )
    await callback.answer()


# ============================================================
# 🏪 АПТЕКИ
# ============================================================

@router.callback_query(F.data.startswith("apothecary_"), PrescriptionFSM.choose_apothecary)
async def process_apothecary(
        callback: types.CallbackQuery,
        state: FSMContext,
        pharmacy_repo: PharmacyRepository
):
    apt_id = int(callback.data.split("_")[-1])

    # Снова обращаемся к БД вместо парсинга кнопок
    apt = await pharmacy_repo.get_apothecary_by_id(apt_id)
    if not apt:
        return await callback.answer("❌ Аптека не найдена", show_alert=True)

    # Сохраняем lpu_name для совместимости с отчетами (там ожидается это поле)
    await state.update_data(
        apt_id=apt_id,
        lpu_name=apt.name
    )

    await callback.message.edit_text(
        f"🏪 <b>{apt.name}</b>\n\n📩 Есть ли заявка на препараты?",
        reply_markup=inline_buttons.get_confirm_inline()
    )
    await callback.answer()