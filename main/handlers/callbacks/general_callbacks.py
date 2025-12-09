from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from typing import Optional

# Импорты состояний
from states.add.prescription_state import PrescriptionFSM
from states.add.add_state import AddDoctor
from states.menu.main_menu_state import MainMenu

# Импорты базы и утилит
from loader import accountantDB, pharmacyDB
from storage.temp_data import TempDataManager
from loader import reportsDB
from utils.logger.logger_config import logger

# Импорты клавиатур (Только Inline!)
from keyboard.inline import inline_buttons, inline_select, menu_kb

router = Router()


# ============================================================
# 🏠 ГЛАВНОЕ МЕНЮ (Обработка нажатий)
# ============================================================

@router.callback_query(F.data == "menu_route")
async def on_menu_route(callback: types.CallbackQuery, state: FSMContext):
    """Нажата кнопка 'Маршрут (Врачи)'"""
    # Устанавливаем целевое состояние (выбор ЛПУ)
    await state.set_state(PrescriptionFSM.choose_lpu)

    # Получаем список районов для врачей
    keyboard = await inline_buttons.get_district_inline(state, mode="district")

    await callback.message.edit_text(
        "📍 <b>Раздел: Маршрут (Врачи)</b>\nВыберите район:",
        reply_markup=keyboard
    )
    await callback.answer()


@router.callback_query(F.data == "menu_pharmacy")
async def on_menu_pharmacy(callback: types.CallbackQuery, state: FSMContext):
    """Нажата кнопка 'Аптека'"""
    # Устанавливаем целевое состояние (выбор Аптеки)
    await state.set_state(PrescriptionFSM.choose_apothecary)

    # Получаем список районов для аптек
    keyboard = await inline_buttons.get_district_inline(state, mode="a_district")

    await callback.message.edit_text(
        "🏥 <b>Раздел: Аптека</b>\nВыберите район:",
        reply_markup=keyboard
    )
    await callback.answer()


@router.callback_query(F.data == "report_all")
async def on_report_menu(callback: types.CallbackQuery):
    """Нажата кнопка 'Отчёты'"""
    # Предполагается, что get_reports_inline существует в inline_buttons
    keyboard = inline_buttons.get_reports_inline()
    await callback.message.edit_text(
        "📊 <b>Отчёты</b>\nВыберите тип отчёта:",
        reply_markup=keyboard
    )
    await callback.answer()


@router.callback_query(F.data == "feedback_view")
async def on_feedback_menu(callback: types.CallbackQuery):
    """Нажата кнопка 'Отзывы'"""
    # Заглушка или меню отзывов
    await callback.message.edit_text(
        "✍️ <b>Раздел отзывов</b>\nФункционал в разработке.",
        reply_markup=menu_kb.get_main_menu_inline()  # Вернуться в меню
    )
    await callback.answer()


@router.callback_query(F.data == "user_log_out")
async def on_logout(callback: types.CallbackQuery, state: FSMContext):
    """Выход из системы"""
    user_id = callback.from_user.id
    try:
        await accountantDB.logout_user(user_id)
    except Exception as e:
        logger.error(f"Logout error: {e}")

    await state.clear()

    # Показываем меню гостя (или просто сообщение)
    await callback.message.edit_text(
        "🚪 Вы успешно вышли из системы.",
        reply_markup=menu_kb.get_guest_menu_inline()
    )
    await callback.answer()


# ============================================================
# 🔙 КНОПКА "НАЗАД" (Глобальная)
# ============================================================
@router.callback_query(F.data == "back_to_main")
async def back_to_main_menu(callback: types.CallbackQuery, state: FSMContext):
    """Возвращает пользователя в главное меню из любого раздела"""
    await state.clear()  # Сбрасываем выбор (район, врач и т.д.)
    await state.set_state(MainMenu.logged_in)

    await callback.message.edit_text(
        "🔙 <b>Главное меню</b>\nВыберите раздел:",
        reply_markup=menu_kb.get_main_menu_inline()
    )
    await callback.answer()


# ============================================================
# 🗺 НАВИГАЦИЯ (Районы -> Маршруты -> Объекты)
# ============================================================

# 1. Выбор Района (Единый обработчик)
@router.callback_query(F.data.contains("district_"))
async def process_district(callback: types.CallbackQuery, state: FSMContext):
    # Определяем режим: Аптека или Врач
    is_pharmacy = callback.data.startswith("a_district_")

    # Парсим ID и Имя
    raw_id = callback.data.split("_")[-1]
    name = await TempDataManager.get_button_name(state, callback.data) or "Район"

    # Сохраняем в TempData
    key = "district"
    await TempDataManager.set(state, key, raw_id)

    # Следующий шаг: Выбор маршрута
    mode = "a_road" if is_pharmacy else "road"
    keyboard = await inline_buttons.get_road_inline(state=state, mode=mode)

    await callback.message.edit_text(
        f"✅ Район: <b>{name}</b>\n🗺 Выберите маршрут:",
        reply_markup=keyboard
    )
    await callback.answer()


# 2. Выбор Маршрута (Единый обработчик)
@router.callback_query(F.data.contains("road_"))
async def process_road(callback: types.CallbackQuery, state: FSMContext):
    is_pharmacy = callback.data.startswith("a_road_")
    road_num = callback.data.split("_")[-1]

    await TempDataManager.set(state, "road", road_num)

    # Получаем район, чтобы отфильтровать объекты в БД
    dist_key = "district"
    district = await TempDataManager.get(state, dist_key)

    msg_text = f"✅ Маршрут: <b>{road_num}</b>\n"

    if is_pharmacy:
        # --> Идем к выбору Аптеки
        await state.set_state(PrescriptionFSM.choose_apothecary)
        keyboard = await inline_buttons.get_apothecary_inline(state, district, road_num)
        msg_text += "🏪 Выберите Аптеку:"
    else:
        # --> Идем к выбору ЛПУ
        await state.set_state(PrescriptionFSM.choose_lpu)
        keyboard = await inline_buttons.get_lpu_inline(state, district, road_num)
        msg_text += "🏥 Выберите ЛПУ:"

    await callback.message.edit_text(msg_text, reply_markup=keyboard)
    await callback.answer()


# ============================================================
# 🏥 ЛПУ и ВРАЧИ
# ============================================================
@router.callback_query(F.data.startswith("lpu_"), PrescriptionFSM.choose_lpu)
async def process_lpu(callback: types.CallbackQuery, state: FSMContext):
    lpu_id = callback.data.split("_")[-1]
    lpu_name = await TempDataManager.get_button_name(state, callback.data)

    await TempDataManager.set(state, "lpu_id", lpu_id)
    await TempDataManager.set(state, "lpu_name", lpu_name)

    # Переход к врачу
    await state.set_state(PrescriptionFSM.choose_doctor)

    # Пробуем достать ссылку 2GIS
    extra = await TempDataManager.get_extra(state, callback.data)
    url_info = ""
    if extra and extra.get('url'):
        url_info = f"\n🔗 <a href='{extra['url']}'>Открыть в 2GIS</a>"

    keyboard = await inline_buttons.get_doctors_inline(state, lpu_id)

    await callback.message.edit_text(
        f"🏥 <b>{lpu_name}</b>{url_info}\n\n👨‍⚕️ Выберите врача:",
        reply_markup=keyboard,
        disable_web_page_preview=True
    )
    await callback.answer()


@router.callback_query(F.data.startswith("doc_"), PrescriptionFSM.choose_doctor)
async def process_doctor(callback: types.CallbackQuery, state: FSMContext):
    doc_id = callback.data.split("_")[-1]
    doc_name = await pharmacyDB.get_doctor_name(doc_id)
    user_name = callback.from_user.full_name  # Get current user name

    await TempDataManager.set(state, "doc_id", doc_id)
    await TempDataManager.set(state, "doc_name", doc_name)

    # 1. Get Doctor Stats (Existing Logic)
    row = await pharmacyDB.get_doc_stats(int(doc_id))
    if row:
        await TempDataManager.set(state, "doc_spec", row["spec"])
        await TempDataManager.set(state, "doc_num", row["numb"])
    else:
        logger.warning(f"Stats not found for doc {doc_id}")

    # ---------------------------------------------------------
    # 🆕 NEW LOGIC: FETCH & FORMAT PREVIOUS REPORT
    # ---------------------------------------------------------
    last_report = await reportsDB.get_last_doctor_report(user_name, doc_name)

    report_text = ""
    if last_report:
        # Format the list of drugs
        preps_str = "\n".join([f"• {p}" for p in last_report['preps']]) if last_report['preps'] else "—"

        report_text = (
            f"📅 <b>Предыдущий отчёт ({last_report['date']}):</b>\n"
            f"📝 <b>Условия:</b> {last_report['term']}\n"
            f"💊 <b>Препараты:</b>\n{preps_str}\n"
            f"💬 <b>Комментарий:</b> {last_report['commentary']}\n"
            f"➖➖➖➖➖➖➖➖➖➖\n\n"
        )
    # ---------------------------------------------------------

    # Transition to Meds
    await state.set_state(PrescriptionFSM.choose_meds)

    await TempDataManager.set(state, "prefix", "doc")
    await TempDataManager.set(state, "selected_items", [])

    keyboard = await inline_select.get_prep_inline(state, prefix="doc")

    # Show the report text ABOVE the doctor name
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
    apt_name = await TempDataManager.get_button_name(state, callback.data)

    # Используем lpu_name как ключ для названия точки (унификация для отчета)
    await TempDataManager.set(state, "lpu_name", apt_name)

    # Спрашиваем про заявку (Да/Нет)
    # Остаемся в том же стейте или переходим в промежуточный?
    # Останемся в choose_apothecary, так как кнопки Yes/No обрабатываются в generic handler ниже

    await callback.message.edit_text(
        f"🏪 <b>{apt_name}</b>\n\n📩 Есть ли заявка на препараты?",
        reply_markup=inline_buttons.get_confirm_inline()
    )
    await callback.answer()


# ============================================================
# ✅ ПОДТВЕРЖДЕНИЕ (Unified Yes/No)
# ============================================================
@router.callback_query(F.data.in_(["confirm_yes", "confirm_no"]))
async def handle_confirmation(callback: types.CallbackQuery, state: FSMContext):
    """
    Обрабатывает Да/Нет для разных сценариев
    """
    is_yes = (callback.data == "confirm_yes")
    current_state = await state.get_state()

    logger.debug(f"Confirmation: {callback.data} | State: {current_state}")

    # 1. Сценарий Аптеки: "Есть ли заявка?"
    if current_state == PrescriptionFSM.choose_apothecary.state:

        # 🔥 FIX: Всегда устанавливаем prefix="apt", даже если нажали НЕТ
        await TempDataManager.set(state, "prefix", "apt")

        if is_yes:
            # ДА: Идем выбирать препараты -> вводим кол-во -> вводим остатки
            await state.set_state(PrescriptionFSM.choose_meds)

            keyboard = await inline_select.get_prep_inline(state, prefix="apt")
            await callback.message.edit_text("💊 Выберите препараты из списка:", reply_markup=keyboard)
        else:
            # НЕТ: Это просто визит без заявки
            # 🔥 FIX: Устанавливаем нули, чтобы в отчете не было "None"
            await TempDataManager.set(state, "quantity", 0)
            await TempDataManager.set(state, "remaining", 0)
            await TempDataManager.set(state, "selected_items", [])  # Препараты не выбраны

            # Пропускаем выбор препаратов и ввод чисел -> сразу к комментарию
            await callback.message.edit_text("👌 Хорошо, визит без заявки.")
            await state.set_state(PrescriptionFSM.pharmacy_comments)
            await callback.message.answer("✍️ Напишите комментарий к визиту:")

        await callback.answer()
        return

    # 2. Сценарий Добавления Врача (AddDoctor)
    if current_state == AddDoctor.waiting_for_confirmation.state:
        if is_yes:
            await callback.message.edit_text("✅ Врач успешно добавлен!")
            # Тут можно вызвать функцию сохранения в БД, если она еще не вызывалась
        else:
            await callback.message.edit_text("❌ Добавление отменено.")
        await state.clear()
        await callback.answer()
        return