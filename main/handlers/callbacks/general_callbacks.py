from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from typing import Optional

# Импорты состояний
from states.add.prescription_state import PrescriptionFSM
from states.add.add_state import AddDoctor
from states.menu.main_menu_state import MainMenu

# Импорты базы (ТОЛЬКО КЛАССЫ)
from db.database import BotDB
from db.reports import ReportRepository

from storage.temp_data import TempDataManager
from utils.logger.logger_config import logger

# Импорты клавиатур
from keyboard.inline import inline_buttons, inline_select, menu_kb, admin_kb

router = Router()


# ============================================================
# 🏠 ГЛАВНОЕ МЕНЮ (Обработка нажатий)
# ============================================================

@router.callback_query(F.data == "menu_route")
async def on_menu_route(callback: types.CallbackQuery, state: FSMContext, pharmacy_db: BotDB):
    """Нажата кнопка 'Маршрут (Врачи)'"""
    await state.set_state(PrescriptionFSM.choose_lpu)

    # Передаем pharmacy_db!
    keyboard = await inline_buttons.get_district_inline(pharmacy_db, state, mode="district")

    await callback.message.edit_text(
        "📍 <b>Раздел: Маршрут (Врачи)</b>\nВыберите район:",
        reply_markup=keyboard
    )
    await callback.answer()


@router.callback_query(F.data == "menu_pharmacy")
async def on_menu_pharmacy(callback: types.CallbackQuery, state: FSMContext, pharmacy_db: BotDB):
    """Нажата кнопка 'Аптека'"""
    await state.set_state(PrescriptionFSM.choose_apothecary)

    # Передаем pharmacy_db!
    keyboard = await inline_buttons.get_district_inline(pharmacy_db, state, mode="a_district")

    await callback.message.edit_text(
        "🏥 <b>Раздел: Аптека</b>\nВыберите район:",
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
    # Нужно передать reports_db в меню
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


@router.callback_query(F.data == "user_log_out")
async def on_logout(callback: types.CallbackQuery, state: FSMContext, accountant_db: BotDB):
    """Выход из системы"""
    user_id = callback.from_user.id
    try:
        # Используем переданный accountant_db
        await accountant_db.logout_user(user_id)
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

    # Передаем reports_db для счетчика задач
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
async def process_district(callback: types.CallbackQuery, state: FSMContext, pharmacy_db: BotDB):
    is_pharmacy = callback.data.startswith("a_district_")

    # Получаем имя района из кэша (если есть) или заглушку
    # Для улучшения: можно сделать fetch имени из БД, но это +1 запрос.
    # Пока оставим как есть, TempData должна работать.
    name = await TempDataManager.get_button_name(state, callback.data) or "Район"

    raw_id = callback.data.split("_")[-1]

    key = "district"
    await TempDataManager.set(state, key, raw_id)

    mode = "a_road" if is_pharmacy else "road"
    # Передаем pharmacy_db!
    keyboard = await inline_buttons.get_road_inline(pharmacy_db, state, mode=mode)

    await callback.message.edit_text(
        f"✅ Район: <b>{name}</b>\n🗺 Выберите маршрут:",
        reply_markup=keyboard
    )
    await callback.answer()


@router.callback_query(F.data.contains("road_"))
async def process_road(callback: types.CallbackQuery, state: FSMContext, pharmacy_db: BotDB):
    is_pharmacy = callback.data.startswith("a_road_")
    road_num = callback.data.split("_")[-1]

    await TempDataManager.set(state, "road", road_num)

    dist_key = "district"
    district = await TempDataManager.get(state, dist_key)

    msg_text = f"✅ Маршрут: <b>{road_num}</b>\n"

    if is_pharmacy:
        await state.set_state(PrescriptionFSM.choose_apothecary)
        # Передаем pharmacy_db!
        keyboard = await inline_buttons.get_apothecary_inline(pharmacy_db, state, district, road_num)
        msg_text += "🏪 Выберите Аптеку:"
    else:
        await state.set_state(PrescriptionFSM.choose_lpu)
        # Передаем pharmacy_db!
        keyboard = await inline_buttons.get_lpu_inline(pharmacy_db, state, district, road_num)
        msg_text += "🏥 Выберите ЛПУ:"

    await callback.message.edit_text(msg_text, reply_markup=keyboard)
    await callback.answer()


# ============================================================
# 🏥 ЛПУ и ВРАЧИ (Выбор из списка)
# ============================================================
@router.callback_query(F.data.startswith("lpu_"), PrescriptionFSM.choose_lpu)
async def process_lpu(callback: types.CallbackQuery, state: FSMContext, pharmacy_db: BotDB):
    lpu_id = callback.data.split("_")[-1]
    lpu_name = await TempDataManager.get_button_name(state, callback.data) or "ЛПУ"

    await TempDataManager.set(state, "lpu_id", lpu_id)
    await TempDataManager.set(state, "lpu_name", lpu_name)

    await state.set_state(PrescriptionFSM.choose_doctor)

    extra = await TempDataManager.get_extra(state, callback.data)
    url_info = ""
    if extra and extra.get('url'):
        url_info = f"\n🔗 <a href='{extra['url']}'>Открыть в 2GIS</a>"

    # Передаем pharmacy_db!
    keyboard = await inline_buttons.get_doctors_inline(pharmacy_db, state, int(lpu_id))

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
        pharmacy_db: BotDB,
        reports_db: ReportRepository
):
    doc_id = callback.data.split("_")[-1]

    # Получаем имя врача из БД
    doc_name = await pharmacy_db.get_doctor_name(doc_id)

    user_name = callback.from_user.full_name  # Или из БД/state

    await TempDataManager.set(state, "doc_id", doc_id)
    await TempDataManager.set(state, "doc_name", doc_name)

    # 1. Получаем статистику врача
    row = await pharmacy_db.get_doc_stats(int(doc_id))
    if row:
        await TempDataManager.set(state, "doc_spec", row["spec"])
        await TempDataManager.set(state, "doc_num", row["numb"])
    else:
        logger.warning(f"Stats not found for doc {doc_id}")

    # 2. Получаем последний отчет (через reports_db)
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

    # Передаем pharmacy_db!
    keyboard = await inline_select.get_prep_inline(pharmacy_db, state, prefix="doc")

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
# ✅ ПОДТВЕРЖДЕНИЕ (Unified Yes/No)
# ============================================================
@router.callback_query(F.data.in_(["confirm_yes", "confirm_no"]))
async def handle_confirmation(
        callback: types.CallbackQuery,
        state: FSMContext,
        pharmacy_db: BotDB  # Добавляем на случай, если внутри get_prep_inline понадобится
):
    is_yes = (callback.data == "confirm_yes")
    current_state = await state.get_state()

    # 1. Сценарий Аптеки: "Есть ли заявка?"
    if current_state == PrescriptionFSM.choose_apothecary.state:

        await TempDataManager.set(state, "prefix", "apt")

        if is_yes:
            await state.set_state(PrescriptionFSM.choose_meds)

            # Передаем pharmacy_db!
            keyboard = await inline_select.get_prep_inline(pharmacy_db, state, prefix="apt")
            await callback.message.edit_text("💊 Выберите препараты из списка:", reply_markup=keyboard)
        else:
            # Пустая заявка
            await TempDataManager.set(state, "quantity", 0)
            await TempDataManager.set(state, "remaining", 0)
            await TempDataManager.set(state, "selected_items", [])

            await callback.message.edit_text("👌 Хорошо, визит без заявки.")
            await state.set_state(PrescriptionFSM.pharmacy_comments)
            await callback.message.answer("✍️ Напишите комментарий к визиту:")

        await callback.answer()
        return

    # 2. Сценарий Добавления Врача (AddDoctor)
    if current_state == AddDoctor.waiting_for_confirmation.state:
        if is_yes:
            await callback.message.edit_text("✅ Врач успешно добавлен!")
        else:
            await callback.message.edit_text("❌ Добавление отменено.")
        await state.clear()
        await callback.answer()
        return