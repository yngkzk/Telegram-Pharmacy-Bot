from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from aiogram.types import ReplyKeyboardRemove

from keyboard.inline import inline_buttons, inline_select
from keyboard.reply import reply_buttons
from pandas import value_counts

from states.menu.main_menu_state import MainMenu
from states.add.add_state import AddDoctor, AddPharmacy
from states.add.prescription_state import PrescriptionFSM

from loader import accountantDB, pharmacyDB
from storage.temp_data import TempDataManager

from utils.logger.logger_config import logger


router = Router()

# === Подтверждение ===
@router.callback_query(F.data == "confirm_yes")
async def confirm_yes(callback: types.CallbackQuery, state: FSMContext):
    current_state = await state.get_state()
    logger.debug(f"FSM state in 'current_state' = {current_state}")

    # Проверяем, в каком состоянии находимся
    if current_state == AddDoctor.waiting_for_spec:
        fio = await TempDataManager.get(state, key="tp_dr_name")
        await state.set_state(AddDoctor.waiting_for_spec)
        keyboard = await inline_buttons.get_spec_inline(state)
        logger.info(f"general_callbacks.py - {keyboard}")
        await callback.message.edit_text(f"👨‍⚕️ Врач {fio}, выберите специальность",
                                         reply_markup=keyboard)
        logger.info(f"Дошел до current_state == WFS - 👨‍⚕️ Врач {fio}")

    elif current_state == PrescriptionFSM.choose_request:
        # Задаю новый state
        await state.set_state(PrescriptionFSM.choose_meds)

        # LOG
        logger.info(f"Дошел до кода PrescriptionFSM")

        # Отвечаем пользователю
        await callback.message.answer(f"👨‍⚕️ Выберите препараты",
                                      reply_markup=inline_select.get_prep_inline())

    elif current_state == AddDoctor.waiting_for_bd:
        fio = TempDataManager.get(state, key="tp_dr_name")
        logger.info(f"Подтверждение - {fio}")
        # Пользователь должен еще добавить специальность врача и его номер (при наличии)
        await callback.message.edit_text(f"👨‍⚕️ Врач {fio} успешно добавлен ✅")

    elif current_state == AddPharmacy.waiting_for_confirmation.state:
        name = data.get("name")
        add_pharmacy_to_db(name)
        await callback.message.edit_text(f"🏥 Аптека {name} успешно добавлена ✅")

    else:
        await callback.message.edit_text("✅ Подтверждено, но действие не определено.")

    await callback.answer()

# === Отмена ===
@router.callback_query(F.data == "confirm_no")
async def confirm_no(callback: types.CallbackQuery, state: FSMContext):
    current_state = await state.get_state()

    # Можно вернуть пользователя в нужный шаг
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

# === Меню пользователя ===
@router.callback_query(F.data == "user_road")
async def user_road(callback: types.CallbackQuery, state: FSMContext):
    # Создаем клавиатуру
    keyboard = await inline_buttons.get_district_inline(state, mode="district")

    await callback.message.edit_text(
        "📍 Вы открыли раздел 'Маршрут'\nВыберите район.",
        reply_markup=keyboard
    )
    await state.set_state(PrescriptionFSM.choose_lpu)

    # LOG
    logger.debug(f"Current FSM - {await state.get_state()}")


@router.callback_query(F.data == "user_apothecary")
async def user_apothecary(callback: types.CallbackQuery, state: FSMContext):
    # Создаем клавиатуру
    keyboard = await inline_buttons.get_district_inline(state, mode="a_district")

    await callback.message.edit_text(
        "📍 Вы открыли раздел 'Аптека'\nВыберите район.",
        reply_markup=keyboard
    )

@router.callback_query(F.data == "user_lpu")
async def user_lpu(callback: types.CallbackQuery, state: FSMContext):

    # Беру данные из временной БД
    district = await TempDataManager.get(state, key="district")
    road = await TempDataManager.get(state, key="road")

    # LOG
    logger.debug(f"Current FSM - {await state.get_state()}")

    if district and road:
        await state.set_state(PrescriptionFSM.choose_lpu)
        keyboard = await inline_buttons.get_lpu_inline(state, district, road)
        await callback.message.edit_text("📍 Выберите ЛПУ",
                                         reply_markup=keyboard)
    else:
        keyboard = await inline_buttons.get_district_inline(state=state,
                                                            mode="district")
        await callback.message.edit_text("🏥 Сначала выберите маршрут!",
                                         reply_markup=keyboard)


@router.callback_query(F.data == "user_log_out")
async def user_log_out(callback: types.CallbackQuery, state: FSMContext):
    """
    При выходе из аккаунта:
    - очищаем FSM состояние
    - отмечаем в БД, что пользователь вышел
    - возвращаем в главное меню (через show_main_menu)
    """
    user_id = callback.from_user.id
    accountantDB.logout_user(user_id)
    await state.clear()
    await callback.answer("🚪 Вы вышли из аккаунта.")
    await callback.message.edit_text("Вы вышли из учётной записи.")
    await show_main_menu(callback, state, logged_in=False)


# === Отчёты ===
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


# === Обратная связь ===
@router.callback_query(F.data == "feedback_add")
async def feedback_add(callback: types.CallbackQuery):
    await callback.message.edit_text("✍️ Напишите свой отзыв сюда...")


@router.callback_query(F.data == "feedback_view")
async def feedback_view(callback: types.CallbackQuery):
    await callback.message.edit_text("📋 Список отзывов пока пуст.")


# === Кнопка Назад ===
@router.callback_query(F.data == "back")
async def back(callback: types.CallbackQuery, state: FSMContext):
    """
    Возвращает в главное меню — учитывая, авторизован ли пользователь.
    """
    user_id = callback.from_user.id
    is_logged_in = accountantDB.is_logged_in(user_id)
    await show_main_menu(callback, state, logged_in=is_logged_in)


# === Универсальная функция возврата в главное меню ===
async def show_main_menu(callback_or_message, state: FSMContext, logged_in: bool):
    """
    Универсальная функция возврата в главное меню.
    Работает как с CallbackQuery, так и с обычным Message.
    """
    if logged_in:
        await state.set_state(MainMenu.logged_in)
        markup = reply_buttons.get_main_kb()
        text = "🔙 Главное меню (авторизованный пользователь)"
    else:
        await state.set_state(MainMenu.main)
        markup = reply_buttons.get_main_kb()
        text = "🔙 Главное меню"

    # Убираем "часики" и отправляем меню
    if isinstance(callback_or_message, types.CallbackQuery):
        await callback_or_message.answer()
        await callback_or_message.message.answer(text,
                                                 reply_markup=markup)
    else:
        await callback_or_message.answer(text,
                                         reply_markup=markup)


# === Выбор района ===
@router.callback_query(F.data.startswith("district_"))
async def district_selected(callback: types.CallbackQuery, state: FSMContext):
    # Извлекаем название района
    district = callback.data.replace("district_", "")
    district_name = await TempDataManager.get_button_name(state, callback.data)

    # Сохраняем выбор в FSMContext
    await TempDataManager.set(state, key="district", value=district)

    # LOG
    logger.debug(f"Current FSM - {await state.get_state()}")

    # Создаем клавиатуру
    keyboard = await inline_buttons.get_road_inline(state=state, mode="road")

    # Отвечаем пользователю
    await callback.message.answer(text=f"✅ Вы выбрали район: {district_name}")
    await callback.message.edit_text(text="🗺 Выберите маршрут",
                                     reply_markup=keyboard)

@router.callback_query(F.data.startswith("a_district_"))
async def a_district_selected(callback: types.CallbackQuery, state: FSMContext):
    # Извлекаем название района
    a_district = callback.data.replace("a_district_", "")
    a_district_name = await TempDataManager.get_button_name(state, callback.data)

    # Сохраняем выбор в FSMContext
    await TempDataManager.set(state, key="a_district", value=a_district)

    # LOG
    logger.debug(f"Current FSM - {await state.get_state()}")

    # Создаем клавиатуру
    keyboard = await inline_buttons.get_road_inline(state=state, mode="a_road")

    # Отвечаем пользователю
    await callback.message.answer(text=f"✅ Вы выбрали район: {a_district_name}")
    await callback.message.edit_text(text="🗺 Выберите маршрут",
                                     reply_markup=keyboard)


# === Выбор маршрута ====
@router.callback_query(F.data.startswith("road_"))
async def road_selected(callback: types.CallbackQuery, state: FSMContext):
    # Извлекаем название маршрута
    road_num = callback.data.replace("road_", "")

    # Сохраняем выбор в FSMContext
    await TempDataManager.set(state, key="road", value=road_num)

    # Вытаскиваем район
    district = await TempDataManager.get(state, key="district")

    # LOG
    logger.debug(f"Current FSM - {await state.get_state()}")
    logger.info(f"Район - {district}, Номер маршрута - {road_num}")

    # Создаем клавиатуру
    keyboard = await inline_buttons.get_lpu_inline(state, district, road_num)

    # Отвечаем пользователю
    await callback.message.answer(text=f"✅ Вы выбрали маршрут № - {road_num}")
    await callback.message.edit_text(text="📍 Выберите ЛПУ",
                                     reply_markup=keyboard)

@router.callback_query(F.data.startswith("a_road_"))
async def road_selected(callback: types.CallbackQuery, state: FSMContext):
    # Извлекаем название маршрута
    a_road_num = callback.data.replace("a_road_", "")

    # Сохраняем выбор в FSMContext
    await TempDataManager.set(state, key="road", value=a_road_num)

    # Вытаскиваем район
    a_district = await TempDataManager.get(state, key="a_district")

    # LOG
    logger.debug(f"Current FSM - {await state.get_state()}")
    logger.info(f"Район - {a_district}, Номер маршрута - {a_road_num}")

    # Задаем новое состояние
    await state.set_state(PrescriptionFSM.choose_apothecary)

    # Создаем клавиатуру
    keyboard = await inline_buttons.get_apothecary_inline(state, a_district, a_road_num)

    # Отвечаем пользователю
    await callback.message.answer(text=f"✅ Вы выбрали маршрут № - {a_road_num}")
    await callback.message.edit_text(text="📍 Выберите Аптеку",
                                     reply_markup=keyboard)


# === Выбор Аптеки ===
@router.callback_query(F.data.startswith("apothecary"), PrescriptionFSM.choose_apothecary)
async def apothecary_selected(callback: types.CallbackQuery, state: FSMContext):
    # Извлекаем название аптеки
    apothecary = await TempDataManager.get_button_name(state, callback.data)

    # Сохраняем выбор в FSMContext
    await TempDataManager.set(state, key="apothecary", value=apothecary)

    # LOG
    logger.debug(f"Current FSM - {await state.get_state()}")
    logger.info(f"Аптека - {apothecary}")

    # Задаем новое состояние
    await state.set_state(PrescriptionFSM.choose_request)

    # Отвечаем пользователю
    await callback.message.answer(text=f"📍 Вы выбрали Аптеку - {apothecary}")
    await callback.message.edit_text(text="📩 Есть ли заявка?", reply_markup=inline_buttons.get_confirm_inline())


# === Выбор ЛПУ ===
@router.callback_query(F.data.startswith("lpu_"), PrescriptionFSM.choose_lpu)
async def lpu_selected(callback: types.CallbackQuery, state: FSMContext):
    # Извлекаем название и ID ЛПУ
    lpu_name = await TempDataManager.get_button_name(state, callback.data)
    lpu_url = await TempDataManager.get_extra(state, callback.data)

    lpu_id = callback.data.replace("lpu_", "")

    # Сохраняем выбор в FSMContext
    await TempDataManager.set(state, key="lpu_name", value=lpu_name)
    await TempDataManager.set(state, key="lpu_id", value=lpu_id)

    # Задаю новый FSM
    await state.set_state(PrescriptionFSM.choose_doctor)

    # LOG
    logger.debug(f"Current FSM - {await state.get_state()}")
    logger.info(f"urls - {lpu_url["url"]}")
    logger.info(f"lpu_selected - {lpu_name}, {lpu_id}")

    # Создаем клавиатуру
    keyboard = await inline_buttons.get_doctors_inline(state, lpu_id)

    # Отвечаем пользователю
    await callback.message.answer(text=f"✅ Вы выбрали ЛПУ - {lpu_name}"
                                       f"\nСсылка в 2GIS - {lpu_url["url"]}")
    await callback.message.edit_text(text="🥼 Выберите врача",
                                     reply_markup=keyboard)


# === Выбор Врача ===
@router.callback_query(F.data.startswith("doc_"), PrescriptionFSM.choose_doctor)
async def doc_selected(callback: types.CallbackQuery, state: FSMContext):

    # Извлекаем имя и ID Врача
    doc_name = await TempDataManager.get_button_name(state, callback.data)
    doc_id = callback.data.replace("doc_", "")

    # Сохраняем выбор в FSMContext
    await TempDataManager.set(state, key="doc_name", value=doc_name)
    await TempDataManager.set(state, key="doc_id", value=doc_id)

    # Берем данные из БД
    doc_spec, doc_num = pharmacyDB.get_doc_stats(doc_id)[0]

    # Сохраняем данные в БД
    await TempDataManager.set(state, key="doc_spec", value=doc_spec)
    await TempDataManager.set(state, key="doc_num", value=doc_num)

    # Задаю новый FSM
    await state.set_state(PrescriptionFSM.choose_meds)

    # LOG
    logger.debug(f"Items in DOC_SELECTED == {doc_spec, doc_num}")
    logger.debug(f"Current FSM - {await state.get_state()}")
    logger.info(f"Пользователь {callback.from_user.first_name} - Выбрал врача - {doc_name, doc_id}")

    # Отвечаем пользователю
    await callback.message.answer(text=f"✅ Вы выбрали врача - {doc_name}")
    await TempDataManager.set(state, "selected_items", [])


    await callback.message.edit_text("🏥 Выберите один или несколько препаратов:",
                                     reply_markup=inline_select.get_prep_inline())