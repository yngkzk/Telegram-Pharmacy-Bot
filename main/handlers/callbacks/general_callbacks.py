from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from typing import Optional

from infrastructure.database.db_helper import db_helper
from infrastructure.database.repo.pharmacy_repo import PharmacyRepository
from infrastructure.database.repo.user_repo import UserRepository
from db.reports import ReportRepository

from states.add.prescription_state import PrescriptionFSM
from states.add.add_state import AddDoctor
from states.menu.main_menu_state import MainMenu

from storage.temp_data import TempDataManager
from utils.logger.logger_config import logger

from keyboard.inline import inline_buttons, inline_select, menu_kb, admin_kb

router = Router()


# ============================================================
# 🏠 ГЛАВНОЕ МЕНЮ (Обработка нажатий)
# ============================================================

@router.callback_query(F.data == "menu_route")
async def on_menu_route(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(PrescriptionFSM.choose_lpu)
    user_id = callback.from_user.id

    async for u_session in db_helper.get_user_session():
        user = await UserRepository(u_session).get_user(user_id)
        region = user.region if user else "АЛА"

    async for session in db_helper.get_pharmacy_session():
        districts = await PharmacyRepository(session).get_districts_by_region(region)
        # Передаем префикс 'district' для врачей
        kb = await inline_buttons.get_district_inline(districts, state, prefix="district")
        await callback.message.edit_text("📍 Выберите район:", reply_markup=kb)
    await callback.answer()

@router.callback_query(F.data == "menu_pharmacy")
async def on_menu_pharmacy(callback: types.CallbackQuery, state: FSMContext):
    """Нажата кнопка 'Аптека'"""
    await state.set_state(PrescriptionFSM.choose_apothecary)
    user_id = callback.from_user.id

    region = "АЛА"
    async for u_session in db_helper.get_user_session():
        u_repo = UserRepository(u_session)
        user = await u_repo.get_user(user_id)
        if user and user.region:
            region = user.region

    async for session in db_helper.get_pharmacy_session():
        repo = PharmacyRepository(session)
        districts = await repo.get_districts_by_region(region)

        # 🔥 ВАЖНО: Передаем prefix="a_district" (чтобы хендлер понял, что это аптека)
        keyboard = await inline_buttons.get_district_inline(districts, state, prefix="a_district")

        await callback.message.edit_text(
            f"🏥 <b>Раздел: Аптека</b>\nРегион: {region}\nВыберите район:",
            reply_markup=keyboard
        )
    await callback.answer()

@router.callback_query(F.data == "report_all")
async def on_report_menu(callback: types.CallbackQuery):
    """Нажата кнопка 'Отчёты'"""
    keyboard = inline_buttons.get_reports_inline()
    await callback.message.edit_text(
        "📊 <b>Отчёты</b>\nВыберите тип отчёта:",
        reply_markup=keyboard
    )
    await callback.answer()


@router.callback_query(F.data == "feedback_view")
async def on_feedback_menu(callback: types.CallbackQuery, reports_db: ReportRepository):
    """Нажата кнопка 'Отзывы'"""
    kb = await menu_kb.get_main_menu_inline(callback.from_user.id, reports_db)
    await callback.message.edit_text(
        "✍️ <b>Раздел отзывов</b>\nФункционал в разработке.",
        reply_markup=kb
    )
    await callback.answer()


@router.callback_query(F.data == "admin_panel")
async def on_admin_panel(callback: types.CallbackQuery):
    """Нажата кнопка 'Админка'"""
    keyboard = admin_kb.get_admin_menu()
    await callback.message.edit_text(
        "⚙️ <b>Админ панель</b>\nВыберите действие:",
        reply_markup=keyboard
    )
    await callback.answer()


@router.callback_query(F.data == "user_log_out")
async def on_logout(callback: types.CallbackQuery, state: FSMContext):
    """Выход из системы"""
    user_id = callback.from_user.id
    try:
        # Логаут через репозиторий
        async for session in db_helper.get_user_session():
            repo = UserRepository(session)
            # В репо должен быть метод logout (или update logged_in=0)
            # Если нет - добавь в user_repo.py:
            # async def logout(self, uid): ... update(User).where...
            # Пока сделаем прямой update для примера:
            from infrastructure.database.models.users import User
            from sqlalchemy import update
            await session.execute(update(User).where(User.user_id == str(user_id)).values(logged_in=False))
            await session.commit()

    except Exception as e:
        logger.error(f"Logout error: {e}")

    await state.clear()
    await callback.message.edit_text(
        "🚪 Вы успешно вышли из системы.",
        reply_markup=menu_kb.get_guest_menu_inline()
    )
    await callback.answer()


# ============================================================
# 🔙 КНОПКА "НАЗАД" (Глобальная)
# ============================================================
@router.callback_query(F.data == "back_to_main")
async def back_to_main_menu(callback: types.CallbackQuery, state: FSMContext, reports_db: ReportRepository):
    """Возвращает пользователя в главное меню"""
    await state.clear()
    await state.set_state(MainMenu.logged_in)

    # Тут пока старый reports_db, это ок
    kb = await menu_kb.get_main_menu_inline(callback.from_user.id, reports_db)

    await callback.message.edit_text(
        "🔙 <b>Главное меню</b>\nВыберите раздел:",
        reply_markup=kb
    )
    await callback.answer()


# ============================================================
# 🗺 НАВИГАЦИЯ (Районы -> Маршруты -> Объекты)
# ============================================================

@router.callback_query(F.data.contains("district_"))
async def process_district(callback: types.CallbackQuery, state: FSMContext):
    is_pharmacy = callback.data.startswith("a_district_")
    district_id = int(callback.data.split("_")[-1])

    # Сохраняем ID района, чтобы потом найти дорогу
    await TempDataManager.set(state, "district_id", district_id)

    # Получаем имя для красивого заголовка из кэша кнопок
    name = await TempDataManager.get_button_name(state, callback.data) or "Район"

    # Генерируем фиксированные маршруты 1-7
    prefix = "a_road" if is_pharmacy else "road"
    roads_fixed = [{"id": i, "road_num": i} for i in range(1, 8)]

    kb = await inline_buttons.get_road_inline(roads_fixed, state, prefix=prefix)

    await callback.message.edit_text(
        f"✅ Район: <b>{name}</b>\nВыберите номер маршрута:",
        reply_markup=kb
    )
    await callback.answer()


@router.callback_query(F.data.contains("road_"))
async def process_road(callback: types.CallbackQuery, state: FSMContext):
    is_pharmacy = callback.data.startswith("a_road_")
    road_num = int(callback.data.split("_")[-1])

    # Достаем ID района, который сохранили ранее
    district_id = await TempDataManager.get(state, "district_id")

    if not district_id:
        return await callback.answer("Ошибка: выберите район заново", show_alert=True)

    async for session in db_helper.get_pharmacy_session():
        repo = PharmacyRepository(session)

        # Находим уникальный road_id по ID района и номеру маршрута
        road_id = await repo.get_road_id_by_data(district_id, road_num)

        if not road_id:
            return await callback.answer(f"Маршрут №{road_num} не найден в базе для этого района.", show_alert=True)

        await TempDataManager.set(state, "road_id", road_id)

        # Тянем ЛПУ/Аптеки по этому ID
        lpus = await repo.get_lpus_by_road(road_id)

        if not lpus:
            return await callback.answer("В этом маршруте пока нет данных.", show_alert=True)

        if is_pharmacy:
            await state.set_state(PrescriptionFSM.choose_apothecary)
            kb = await inline_buttons.get_apothecary_inline(lpus, state)
            title = "🏪 Выберите Аптеку:"
        else:
            await state.set_state(PrescriptionFSM.choose_lpu)
            kb = await inline_buttons.get_lpu_inline(lpus, state)
            title = "🏥 Выберите ЛПУ:"

        await callback.message.edit_text(f"✅ Маршрут {road_num}\n{title}", reply_markup=kb)
    await callback.answer()


# ============================================================
# 🏥 ЛПУ и ВРАЧИ (Выбор из списка)
# ============================================================
@router.callback_query(F.data.startswith("lpu_"), PrescriptionFSM.choose_lpu)
async def process_lpu(callback: types.CallbackQuery, state: FSMContext):
    lpu_id = int(callback.data.split("_")[-1])
    lpu_name = await TempDataManager.get_button_name(state, callback.data) or "ЛПУ"

    await TempDataManager.set(state, "lpu_id", lpu_id)
    await TempDataManager.set(state, "lpu_name", lpu_name)

    await state.set_state(PrescriptionFSM.choose_doctor)

    extra = await TempDataManager.get_extra(state, callback.data)
    url_info = ""
    if extra and extra.get('url'):
        url_info = f"\n🔗 <a href='{extra['url']}'>Открыть в 2GIS</a>"

    async for session in db_helper.get_pharmacy_session():
        repo = PharmacyRepository(session)
        doctors = await repo.get_doctors_by_lpu(lpu_id)

        # Передаем список врачей, а не БД
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
        reports_db: ReportRepository
):
    doc_id = int(callback.data.split("_")[-1])
    user_name = callback.from_user.full_name

    async for session in db_helper.get_pharmacy_session():
        repo = PharmacyRepository(session)
        doctor = await repo.get_doctor_by_id(doc_id)

        if not doctor:
            await callback.answer("Врач не найден")
            return

        doc_name = doctor.doctor

        # Сохраняем данные
        await TempDataManager.set(state, "doc_id", doc_id)
        await TempDataManager.set(state, "doc_name", doc_name)

        # Спец и номер
        if doctor.spec_id:
            spec_name = await repo.get_spec_name(doctor.spec_id)
            await TempDataManager.set(state, "doc_spec", spec_name)
        else:
            await TempDataManager.set(state, "doc_spec", "Не указано")

        await TempDataManager.set(state, "doc_num", doctor.numb)

        # Препараты для след. шага
        preps = await repo.get_preps()  # Нужно добавить метод get_preps в repo!

        keyboard = await inline_buttons.build_keyboard_from_items(
            preps, prefix="doc", state=state, row_width=2, add_new_btn_callback="add_prep"
        )

    # Статистика из отчетов (Legacy)
    last_report = await reports_db.get_last_doctor_report(user_name, doc_name)
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
    await TempDataManager.set(state, "prefix", "doc")
    await TempDataManager.set(state, "selected_items", [])

    await callback.message.edit_text(
        f"{report_text}👨‍⚕️ <b>{doc_name}</b>\n💊 Выберите препараты:",
        reply_markup=keyboard
    )
    await callback.answer()


# ============================================================
# 🏪 АПТЕКИ
# ============================================================
@router.callback_query(F.data.startswith("apothecary_"), PrescriptionFSM.choose_apothecary)
async def process_apothecary(callback: types.CallbackQuery, state: FSMContext):
    apt_id = callback.data.split("_")[-1]
    apt_name = await TempDataManager.get_button_name(state, callback.data) or "Аптека"

    await TempDataManager.set(state, "lpu_name", apt_name)

    await callback.message.edit_text(
        f"🏪 <b>{apt_name}</b>\n\n📩 Есть ли заявка на препараты?",
        reply_markup=inline_buttons.get_confirm_inline()
    )
    await callback.answer()


# ============================================================
# ✅ ПОДТВЕРЖДЕНИЕ
# ============================================================
@router.callback_query(F.data.in_(["confirm_yes", "confirm_no"]))
async def handle_confirmation(callback: types.CallbackQuery, state: FSMContext):
    is_yes = (callback.data == "confirm_yes")
    current_state = await state.get_state()

    if current_state == PrescriptionFSM.choose_apothecary.state:
        await TempDataManager.set(state, "prefix", "apt")

        if is_yes:
            await state.set_state(PrescriptionFSM.choose_meds)

            async for session in db_helper.get_pharmacy_session():
                repo = PharmacyRepository(session)
                preps = await repo.get_preps()
                keyboard = await inline_buttons.build_keyboard_from_items(
                    preps, prefix="apt", state=state, row_width=2
                )

            await callback.message.edit_text("💊 Выберите препараты из списка:", reply_markup=keyboard)
        else:
            await TempDataManager.set(state, "quantity", 0)
            await TempDataManager.set(state, "remaining", 0)
            await TempDataManager.set(state, "selected_items", [])
            await callback.message.edit_text("👌 Хорошо, визит без заявки.")
            await state.set_state(PrescriptionFSM.pharmacy_comments)
            await callback.message.answer("✍️ Напишите комментарий к визиту:")

        await callback.answer()
        return

    if current_state == AddDoctor.waiting_for_confirmation.state:
        if is_yes:
            await callback.message.edit_text("✅ Врач успешно добавлен!")
        else:
            await callback.message.edit_text("❌ Добавление отменено.")
        await state.clear()
        await callback.answer()
        return