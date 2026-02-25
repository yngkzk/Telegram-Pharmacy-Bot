from datetime import datetime
from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext

# 🔥 НОВЫЕ ИМПОРТЫ РЕПОЗИТОРИЕВ
from infrastructure.database.repo.pharmacy_repo import PharmacyRepository
from infrastructure.database.repo.report_repo import ReportRepository

# Состояния и клавиатуры
from states.add.prescription_state import PrescriptionFSM
from keyboard.inline import inline_buttons

# Импорты для работы галочек (мульти-выбор)
from handlers.add.select_handlers import ensure_prep_items_loaded
from keyboard.inline.inline_select import build_multi_select_keyboard

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

    # 1. Забираем эталонные данные из базы
    lpu = await pharmacy_repo.get_lpu_by_id(lpu_id)
    if not lpu:
        return await callback.answer("❌ ЛПУ не найдено в базе", show_alert=True)

    # 2. Сохраняем все данные в нативный FSM
    lpu_name = getattr(lpu, 'pharmacy_name', getattr(lpu, 'name', 'Неизвестное ЛПУ'))

    await state.update_data(
        lpu_id=lpu_id,
        lpu_name=lpu_name
    )

    await state.set_state(PrescriptionFSM.choose_doctor)

    url_info = f"\n🔗 <a href='{lpu.url}'>Открыть в 2GIS</a>" if getattr(lpu, 'url', None) else ""

    # Загружаем врачей
    doctors = await pharmacy_repo.get_doctors_by_lpu(lpu_id)
    keyboard = await inline_buttons.get_doctors_inline(doctors, lpu_id=lpu_id, page=1, state=state)

    await callback.message.edit_text(
        f"🏥 <b>{lpu_name}</b>{url_info}\n\n👨‍⚕️ Выберите врача:",
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

    # Достаем специальность (с учетом ORM)
    spec_name = "Не указана"
    specialty = getattr(doctor, 'specialty', None)

    if specialty and getattr(specialty, 'spec', None):
        spec_name = specialty.spec
    else:
        # Фолбэк, если relationship не подгрузился
        actual_spec_id = getattr(doctor, 'spec_id', getattr(doctor, 'main_spec_id', None))
        if actual_spec_id:
            fetched_spec = await pharmacy_repo.get_spec_name(actual_spec_id)
            if fetched_spec:
                spec_name = fetched_spec

    # Массовое обновление стейта
    doc_name = getattr(doctor, 'doctor', 'Неизвестный врач')
    await state.update_data(
        doc_id=doc_id,
        doc_name=doc_name,
        doc_spec=spec_name,
        doc_num=getattr(doctor, 'numb', None),
        prefix="doc",
        selected_items=[]
    )

    # === МАГИЯ ГАЛОЧЕК ===
    # Загружаем препараты через вспомогательную функцию из select_handlers
    items = await ensure_prep_items_loaded(state, pharmacy_repo)

    # Строим ту самую клавиатуру с мульти-выбором
    keyboard = build_multi_select_keyboard(items, [], "doc")

    # Загружаем историю из новой БД
    last_report = await reports_db.get_last_doctor_report(user_name, doc_name)
    report_text = ""

    if last_report:
        # Безопасное извлечение данных из ORM объекта (или словаря, если метод repo еще возвращает dict)
        is_dict = isinstance(last_report, dict)

        raw_date = last_report['date'] if is_dict else getattr(last_report, 'date', None)
        date_str = raw_date.strftime('%d.%m.%Y') if isinstance(raw_date, datetime) else str(raw_date).split(' ')[0]

        term = last_report.get('term', '—') if is_dict else getattr(last_report, 'term', '—')
        commentary = last_report.get('commentary', '—') if is_dict else getattr(last_report, 'commentary', '—')

        # Получаем список препаратов
        preps_data = last_report.get('preps', []) if is_dict else getattr(last_report, 'preps', [])

        if preps_data:
            preps_str = "\n".join([f"• {p if isinstance(p, str) else getattr(p, 'prep_name', p)}" for p in preps_data])
        else:
            preps_str = "—"

        report_text = (
            f"📅 <b>Предыдущий отчёт ({date_str}):</b>\n"
            f"📝 <b>Условия:</b> {term}\n"
            f"💊 <b>Препараты:</b>\n{preps_str}\n"
            f"💬 <b>Комментарий:</b> {commentary}\n"
            f"➖➖➖➖➖➖➖➖➖➖\n\n"
        )

    await state.set_state(PrescriptionFSM.choose_meds)

    await callback.message.edit_text(
        f"{report_text}👨‍⚕️ <b>{doc_name}</b>\n💊 Выберите препараты:",
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

    apt = await pharmacy_repo.get_apothecary_by_id(apt_id)
    if not apt:
        return await callback.answer("❌ Аптека не найдена", show_alert=True)

    apt_name = getattr(apt, 'name', getattr(apt, 'pharmacy_name', 'Неизвестная аптека'))

    await state.update_data(
        apt_id=apt_id,
        lpu_name=apt_name,
        prefix="apt"
    )

    await callback.message.edit_text(
        f"🏪 <b>{apt_name}</b>\n\n📩 Есть ли заявка на препараты?",
        reply_markup=inline_buttons.get_confirm_inline()
    )
    await callback.answer()