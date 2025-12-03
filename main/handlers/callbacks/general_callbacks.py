from typing import Any, Dict, Optional

from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramBadRequest

from keyboard.inline import inline_buttons, inline_select
from keyboard.reply import reply_buttons

from states.menu.main_menu_state import MainMenu
from states.add.add_state import AddDoctor, AddPharmacy
from states.add.prescription_state import PrescriptionFSM

from loader import accountantDB, pharmacyDB
from storage.temp_data import TempDataManager

from utils.logger.logger_config import logger


router = Router()


# -----------------------
# Вспомогательные функции
# -----------------------
async def _safe_get_state_str(state: FSMContext) -> Optional[str]:
    return await state.get_state()


async def _add_pharmacy_from_state(state: FSMContext) -> Optional[str]:
    """
    Попытка добавить аптеку, используя данные в state.
    Возвращает имя добавленной аптеки или None при ошибке.
    """
    data = await state.get_data()
    name = data.get("name")
    road = data.get("road")
    url = data.get("url") or data.get("pharmacy_url")

    if not name:
        return None

    try:
        # Если в вашей БД метод отличается, замените на нужный вызов
        # Здесь ожидается: add_lpu(road_id, pharmacy_name, pharmacy_url)
        await pharmacyDB.add_lpu(road, name, url)
        return name
    except Exception as e:
        logger.exception("Ошибка при добавлении аптеки в БД: %s", e)
        return None


# -----------------------
# Подтверждение (Yes)
# -----------------------
@router.callback_query(F.data == "confirm_yes")
async def confirm_yes(callback: types.CallbackQuery, state: FSMContext):
    current_state = await _safe_get_state_str(state)
    logger.debug("FSM state in 'confirm_yes' = %s", current_state)

    # === Добавление врача: показать список специальностей ===
    if current_state == AddDoctor.waiting_for_spec.state:
        fio = await TempDataManager.get(state, "tp_dr_name")
        # остаёмся на том же шаге — показываем выбор специальности
        keyboard = await inline_buttons.get_spec_inline(state)
        await callback.message.edit_text(f"👨‍⚕️ Врач {fio}, выберите специальность",
                                         reply_markup=keyboard)
        logger.info("Показал выбор специальностей для врача %s", fio)

    # === Переход к выбору препаратов (есть заявка) ===
    elif current_state == PrescriptionFSM.choose_request.state:
        await state.set_state(PrescriptionFSM.choose_meds)
        logger.info("Перехожу в состояние choose_meds для пользователя %s", callback.from_user.id)
        # inline_select.get_prep_inline — async (в нашем рефакторинге)
        keyboard = await inline_select.get_prep_inline(state=state, prefix="apt")
        await callback.message.edit_text("👨‍⚕️ Выберите препараты", reply_markup=keyboard)

    # === Подтверждение добавления врача — завершающий шаг ===
    elif current_state == AddDoctor.waiting_for_bd.state:
        fio = await TempDataManager.get(state, "tp_dr_name")
        # Здесь предполагается, что данные врача уже сохранены ранее (например, в add_doctor_bd handler)
        await callback.message.edit_text(f"👨‍⚕️ Врач {fio} успешно добавлен ✅")
        logger.info("Добавление врача подтверждено: %s", fio)
        await state.clear()

    # === Подтверждение добавления аптеки ===
    elif current_state == AddPharmacy.waiting_for_confirmation.state:
        # Берём данные и пробуем добавить аптеки
        name = await _add_pharmacy_from_state(state)
        if name:
            await callback.message.edit_text(f"🏥 Аптека {name} успешно добавлена ✅")
            logger.info("Аптека добавлена: %s", name)
        else:
            await callback.message.edit_text("⚠️ Не удалось добавить аптеку. Проверьте данные и попробуйте снова.")
            logger.warning("Не удалось добавить аптеку — недостаточно данных")
        await state.clear()

    else:
        await callback.message.edit_text("✅ Подтверждено, но действие не определено.")
        logger.debug("confirm_yes: действие не определено. state=%s", current_state)

    await callback.answer()


# -----------------------
# Отмена (No)
# -----------------------
@router.callback_query(F.data == "confirm_no")
async def confirm_no(callback: types.CallbackQuery, state: FSMContext):
    current_state = await _safe_get_state_str(state)
    logger.debug("FSM state in 'confirm_no' = %s", current_state)

    if current_state == AddDoctor.waiting_for_confirmation.state:
        await state.set_state(AddDoctor.waiting_for_name)
        await callback.message.edit_text("❌ Добавление врача отменено. Введите ФИО заново.",
                                         reply_markup=inline_buttons.get_cancel_inline())

    elif current_state == AddPharmacy.waiting_for_confirmation.state:
        await state.set_state(AddPharmacy.waiting_for_name)
        await callback.message.edit_text("❌ Добавление аптеки отменено. Введите название снова.",
                                         reply_markup=inline_buttons.get_cancel_inline())

    else:
        await callback.message.edit_text("❌ Действие отменено.")

    await callback.answer()


# -----------------------
# Меню пользователя — выбор разделов
# -----------------------
@router.callback_query(F.data == "user_road")
async def user_road(callback: types.CallbackQuery, state: FSMContext):
    keyboard = await inline_buttons.get_district_inline(state, mode="district")
    await callback.message.edit_text(
        "📍 Вы открыли раздел 'Маршрут'\nВыберите район.",
        reply_markup=keyboard
    )
    await state.set_state(PrescriptionFSM.choose_lpu)
    logger.debug("user_road -> state set to choose_lpu for user %s", callback.from_user.id)
    await callback.answer()


@router.callback_query(F.data == "user_apothecary")
async def user_apothecary(callback: types.CallbackQuery, state: FSMContext):
    keyboard = await inline_buttons.get_district_inline(state, mode="a_district")
    await callback.message.edit_text(
        "📍 Вы открыли раздел 'Аптека'\nВыберите район.",
        reply_markup=keyboard
    )
    await callback.answer()


@router.callback_query(F.data == "user_lpu")
async def user_lpu(callback: types.CallbackQuery, state: FSMContext):
    district = await TempDataManager.get(state, "district")
    road = await TempDataManager.get(state, "road")

    logger.debug("user_lpu: district=%s, road=%s, state=%s", district, road, await state.get_state())

    if district and road:
        await state.set_state(PrescriptionFSM.choose_lpu)
        keyboard = await inline_buttons.get_lpu_inline(state, district, road)
        await callback.message.edit_text("📍 Выберите ЛПУ", reply_markup=keyboard)
    else:
        keyboard = await inline_buttons.get_district_inline(state=state, mode="district")
        await callback.message.edit_text("🏥 Сначала выберите маршрут!", reply_markup=keyboard)

    await callback.answer()


@router.callback_query(F.data == "user_log_out")
async def user_log_out(callback: types.CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    try:
        await accountantDB.logout_user(user_id)
    except Exception:
        logger.exception("Ошибка при logout_user для %s", user_id)

    await state.clear()
    await callback.answer("🚪 Вы вышли из аккаунта.")
    await callback.message.edit_text("Вы вышли из учётной записи.")
    await show_main_menu(callback, state, logged_in=False)


# -----------------------
# Отчёты
# -----------------------
@router.callback_query(F.data.in_(["report_sales", "report_income", "report_all"]))
async def handle_reports(callback: types.CallbackQuery):
    data_map = {
        "report_sales": "📊 Раздел 'Продажи'",
        "report_income": "💰 Раздел 'Доходы'",
        "report_all": "🧾 Все отчёты"
    }
    await callback.message.edit_text(
        data_map.get(callback.data, "Раздел не найден."),
        reply_markup=inline_buttons.get_reports_inline()
    )
    await callback.answer()


# -----------------------
# Обратная связь
# -----------------------
@router.callback_query(F.data == "feedback_add")
async def feedback_add(callback: types.CallbackQuery):
    await callback.message.edit_text("✍️ Напишите свой отзыв сюда...")
    await callback.answer()


@router.callback_query(F.data == "feedback_view")
async def feedback_view(callback: types.CallbackQuery):
    await callback.message.edit_text("📋 Список отзывов пока пуст.")
    await callback.answer()


# -----------------------
# Кнопка Назад
# -----------------------
@router.callback_query(F.data == "back")
async def back(callback: types.CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    data = await state.get_data()
    user_name = data.get("username")

    try:
        is_logged_in = await accountantDB.is_logged_in(user_id, user_name)
    except Exception:
        logger.exception("Ошибка при проверке is_logged_in для %s", user_id)
        is_logged_in = False

        # LOG
    logger.info(f"BACK: user_id - {user_id}, user_name - {user_name}")
    logger.info(f"BACK: is_logged_in - {is_logged_in}")

    await show_main_menu(callback, state, logged_in=is_logged_in)
    await callback.answer()


# -----------------------
# Универсальное главное меню
# -----------------------
async def show_main_menu(callback_or_message: Any, state: FSMContext, logged_in: bool):
    if logged_in:
        await state.set_state(MainMenu.logged_in)
        markup = reply_buttons.get_main_kb()
        text = "🔙 Главное меню (авторизованный пользователь)"
    else:
        await state.set_state(MainMenu.main)
        markup = reply_buttons.get_main_kb()
        text = "🔙 Главное меню"

    if isinstance(callback_or_message, types.CallbackQuery):
        await callback_or_message.answer()
        await callback_or_message.message.answer(text, reply_markup=markup)
    else:
        await callback_or_message.answer(text, reply_markup=markup)


# -----------------------
# Выборы: район / маршрут / аптека / ЛПУ / врач
# -----------------------
@router.callback_query(F.data.startswith("district_"))
async def district_selected(callback: types.CallbackQuery, state: FSMContext):
    district = callback.data.replace("district_", "")
    district_name = await TempDataManager.get_button_name(state, callback.data)
    await TempDataManager.set(state, "district", district)

    logger.debug("district_selected -> %s (state=%s)", district, await state.get_state())

    keyboard = await inline_buttons.get_road_inline(state=state, mode="road")
    await callback.message.answer(text=f"✅ Вы выбрали район: {district_name}")
    await callback.message.edit_text(text="🗺 Выберите маршрут", reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data.startswith("a_district_"))
async def a_district_selected(callback: types.CallbackQuery, state: FSMContext):
    a_district = callback.data.replace("a_district_", "")
    a_district_name = await TempDataManager.get_button_name(state, callback.data)
    await TempDataManager.set(state, "a_district", a_district)

    logger.debug("a_district_selected -> %s (state=%s)", a_district, await state.get_state())

    keyboard = await inline_buttons.get_road_inline(state=state, mode="a_road")
    await callback.message.answer(text=f"✅ Вы выбрали район: {a_district_name}")
    await callback.message.edit_text(text="🗺 Выберите маршрут", reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data.startswith("road_"))
async def road_selected(callback: types.CallbackQuery, state: FSMContext):
    road_num = callback.data.replace("road_", "")
    await TempDataManager.set(state, "road", road_num)

    district = await TempDataManager.get(state, "district")
    logger.debug("road_selected -> district=%s, road=%s (state=%s)", district, road_num, await state.get_state())
    logger.info("Район - %s, Номер маршрута - %s", district, road_num)

    keyboard = await inline_buttons.get_lpu_inline(state, district, road_num)
    await callback.message.answer(text=f"✅ Вы выбрали маршрут № - {road_num}")
    await callback.message.edit_text(text="📍 Выберите ЛПУ", reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data.startswith("a_road_"))
async def a_road_selected(callback: types.CallbackQuery, state: FSMContext):
    a_road_num = callback.data.replace("a_road_", "")
    await TempDataManager.set(state, "road", a_road_num)

    a_district = await TempDataManager.get(state, "a_district")
    logger.debug("a_road_selected -> a_district=%s, a_road=%s (state=%s)", a_district, a_road_num, await state.get_state())
    logger.info("Район - %s, Номер маршрута - %s", a_district, a_road_num)

    await state.set_state(PrescriptionFSM.choose_apothecary)
    keyboard = await inline_buttons.get_apothecary_inline(state, a_district, a_road_num)
    await callback.message.answer(text=f"✅ Вы выбрали маршрут № - {a_road_num}")
    await callback.message.edit_text(text="📍 Выберите Аптеку", reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data.startswith("apothecary"), PrescriptionFSM.choose_apothecary)
async def apothecary_selected(callback: types.CallbackQuery, state: FSMContext):
    apothecary = await TempDataManager.get_button_name(state, callback.data)
    await TempDataManager.set(state, "apothecary", apothecary)

    logger.debug("apothecary_selected -> %s (state=%s)", apothecary, await state.get_state())
    logger.info("Аптека - %s", apothecary)

    await state.set_state(PrescriptionFSM.choose_request)
    await callback.message.answer(text=f"📍 Вы выбрали Аптеку - {apothecary}")
    await callback.message.edit_text(text="📩 Есть ли заявка?", reply_markup=inline_buttons.get_confirm_inline())
    await callback.answer()


@router.callback_query(F.data.startswith("lpu_"), PrescriptionFSM.choose_lpu)
async def lpu_selected(callback: types.CallbackQuery, state: FSMContext):
    lpu_name = await TempDataManager.get_button_name(state, callback.data)
    lpu_extra = await TempDataManager.get_extra(state, callback.data) or {}
    lpu_id = callback.data.replace("lpu_", "")

    await TempDataManager.set(state, "lpu_name", lpu_name)
    await TempDataManager.set(state, "lpu_id", lpu_id)

    await state.set_state(PrescriptionFSM.choose_doctor)

    logger.debug("lpu_selected -> name=%s, id=%s (state=%s)", lpu_name, lpu_id, await state.get_state())
    logger.info("lpu_selected - %s, %s", lpu_name, lpu_id)

    url_text = lpu_extra.get("url") if isinstance(lpu_extra, dict) else None
    if url_text:
        await callback.message.answer(text=f"✅ Вы выбрали ЛПУ - {lpu_name}\nСсылка в 2GIS - {url_text}")
    else:
        await callback.message.answer(text=f"✅ Вы выбрали ЛПУ - {lpu_name}")

    keyboard = await inline_buttons.get_doctors_inline(state, lpu_id)
    await callback.message.edit_text(text="🥼 Выберите врача", reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data.startswith("doc_"), PrescriptionFSM.choose_doctor)
async def doc_selected(callback: types.CallbackQuery, state: FSMContext):
    doc_name = await TempDataManager.get_button_name(state, callback.data)
    doc_id = callback.data.replace("doc_", "")

    await TempDataManager.set(state, "doc_name", doc_name)
    await TempDataManager.set(state, "doc_id", doc_id)

    # Берём данные по врачу (async)
    try:
        doc_stats = await pharmacyDB.get_doc_stats(doc_id)
    except Exception:
        logger.exception("Ошибка получения статистики врача %s", doc_id)
        doc_stats = None

    # doc_stats может быть строкой/кортежем/Row — распарсим аккуратно
    doc_spec = None
    doc_num = None
    if doc_stats:
        # Если возвращается кортеж/список или aiosqlite.row
        if isinstance(doc_stats, (list, tuple)):
            # берем первые значения
            if len(doc_stats) >= 1:
                first = doc_stats[0]
                if isinstance(first, (list, tuple)):
                    doc_spec = first[0] if len(first) > 0 else None
                    doc_num = first[1] if len(first) > 1 else None
                elif isinstance(first, dict):
                    doc_spec = first.get("spec")
                    doc_num = first.get("numb")
        elif isinstance(doc_stats, dict):
            doc_spec = doc_stats.get("spec")
            doc_num = doc_stats.get("numb")
        else:
            # Попробуем распаковать как (spec, num)
            try:
                doc_spec, doc_num = doc_stats
            except Exception:
                logger.debug("Непредвиденный формат doc_stats: %s", type(doc_stats))

    await TempDataManager.set(state, "doc_spec", doc_spec)
    await TempDataManager.set(state, "doc_num", doc_num)

    await state.set_state(PrescriptionFSM.choose_meds)

    logger.debug("doc_selected -> spec=%s, num=%s (state=%s)", doc_spec, doc_num, await state.get_state())
    logger.info("Пользователь %s выбрал врача %s (%s)", callback.from_user.first_name, doc_name, doc_id)

    await callback.message.answer(text=f"✅ Вы выбрали врача - {doc_name}")
    await TempDataManager.set(state, "selected_items", [])

    # inline_select.get_prep_inline — async
    keyboard = await inline_select.get_prep_inline(state, prefix="doc")
    await callback.message.edit_text(
        "🏥 Выберите препараты:",
        reply_markup=keyboard
    )
    await callback.answer()
