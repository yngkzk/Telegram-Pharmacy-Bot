from contextlib import suppress
from typing import List, Tuple

from aiogram import Router, types, F
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# Импортируем классы для типов
from db.database import BotDB
from db.reports import ReportRepository

from storage.temp_data import TempDataManager
from keyboard.inline.inline_select import build_multi_select_keyboard, get_prep_inline
from keyboard.inline.inline_buttons import get_doctors_inline, get_confirm_inline
from utils.logger.logger_config import logger
from states.add.prescription_state import PrescriptionFSM

router = Router()


# ============================================================
# 📥 ЗАГРУЗКА И КЭШИРОВАНИЕ ПРЕПАРАТОВ
# ============================================================
async def load_items(state: FSMContext, pharmacy_db: BotDB) -> List[Tuple[int, str]]:
    """
    Загружает список препаратов из БД или кэша состояния.
    """
    items = await TempDataManager.get(state, "prep_items")
    if items is None:
        # Используем переданный объект БД
        raw_rows = await pharmacy_db.get_prep_list()
        items = [(row["id"], row["prep"]) for row in raw_rows]

        prep_map = {item_id: name for item_id, name in items}
        await TempDataManager.set(state, "prep_items", items)
        await TempDataManager.set(state, "prep_map", prep_map)
    return items


# ============================================================
# ☑️ ПЕРЕКЛЮЧЕНИЕ ВЫБОРА (ЧЕКБОКСЫ)
# ============================================================
@router.callback_query(F.data.startswith("select_"), PrescriptionFSM.choose_meds)
async def toggle_selection(callback: types.CallbackQuery, state: FSMContext, pharmacy_db: BotDB):
    try:
        _, prefix, option_id = callback.data.split("_")
        option_id = int(option_id)
    except ValueError:
        await callback.answer("❌ Ошибка данных кнопки")
        return

    # Передаем pharmacy_db в функцию загрузки
    items = await load_items(state, pharmacy_db)

    selected = await TempDataManager.get(state, "selected_items", [])

    if option_id in selected:
        selected.remove(option_id)
    else:
        selected.append(option_id)

    # Используем множество для удаления дублей (на всякий случай)
    selected = list(set(selected))

    await TempDataManager.set(state, "selected_items", selected)

    # Строим новую клавиатуру
    new_keyboard = build_multi_select_keyboard(items, selected, prefix)

    with suppress(TelegramBadRequest):
        await callback.message.edit_reply_markup(reply_markup=new_keyboard)

    await callback.answer()


# ============================================================
# 🔄 СБРОС ВЫБОРА
# ============================================================
@router.callback_query(F.data == "reset_selection", PrescriptionFSM.choose_meds)
async def reset_selection(callback: types.CallbackQuery, state: FSMContext, pharmacy_db: BotDB):
    items = await load_items(state, pharmacy_db)
    prefix = await TempDataManager.get(state, "prefix", "doc")

    await TempDataManager.set(state, "selected_items", [])
    new_keyboard = build_multi_select_keyboard(items, [], prefix)

    with suppress(TelegramBadRequest):
        await callback.message.edit_reply_markup(reply_markup=new_keyboard)

    await callback.answer("🗑 Выбор сброшен")


# ============================================================
# 🏥 ВЫБОР ЛПУ / АПТЕКИ
# ============================================================
@router.callback_query(F.data.startswith("lpu_"), PrescriptionFSM.choose_lpu)
async def process_lpu_selection(callback: types.CallbackQuery, state: FSMContext, pharmacy_db: BotDB):
    """
    Пользователь выбрал ЛПУ (больницу).
    Теперь нужно показать список врачей.
    """
    lpu_id = int(callback.data.split("_")[-1])

    # Пытаемся достать имя из TempData (мы его сохраняли в build_keyboard)
    # Если там нет - ничего страшного, покажем просто "ЛПУ"
    # Для улучшения можно сделать fetch имени из БД, но это лишний запрос
    lpu_name = "Выбранное ЛПУ"

    await TempDataManager.set(state, "lpu_id", lpu_id)
    await TempDataManager.set(state, "lpu_name", lpu_name)

    data = await TempDataManager.get_all(state)
    prefix = data.get("prefix")

    if not prefix:
        prefix = "doc"
        await TempDataManager.set(state, "prefix", "doc")

    # --- ВРАЧ ---
    if prefix == "doc":
        await state.set_state(PrescriptionFSM.choose_doctor)

        # Передаем pharmacy_db в генератор клавиатуры!
        keyboard = await get_doctors_inline(pharmacy_db, state, lpu_id=lpu_id)

        await callback.message.edit_text(
            f"🏥 ЛПУ выбрано.\n👨‍⚕️ Выберите врача:",
            reply_markup=keyboard
        )

    # --- АПТЕКА ---
    elif prefix == "apt":
        await TempDataManager.set(state, "prefix", "apt")

        await state.set_state(PrescriptionFSM.choose_apothecary)
        await callback.message.edit_text(
            f"🏥 ЛПУ выбрано.\n\nЕсть ли заявка на препараты?",
            reply_markup=get_confirm_inline()  # Исправлено название функции
        )

    await callback.answer()


# ============================================================
# 👨‍⚕️ ВЫБОР ВРАЧА
# ============================================================
@router.callback_query(F.data.startswith("doc_"), PrescriptionFSM.choose_doctor)
async def process_doctor(
        callback: types.CallbackQuery,
        state: FSMContext,
        pharmacy_db: BotDB,
        reports_db: ReportRepository
):
    doc_id = int(callback.data.split("_")[-1])
    user_name = callback.from_user.full_name  # Или из БД, если нужно точнее

    # Получаем данные врача через объект БД
    doc_name = await pharmacy_db.get_doctor_name(doc_id)

    await TempDataManager.set(state, "doc_id", doc_id)
    await TempDataManager.set(state, "doc_name", doc_name)

    # Статистика врача
    row = await pharmacy_db.get_doc_stats(doc_id)
    if row:
        await TempDataManager.set(state, "doc_spec", row["spec"])
        await TempDataManager.set(state, "doc_num", row["numb"])
    else:
        await TempDataManager.set(state, "doc_spec", "Не указано")
        await TempDataManager.set(state, "doc_num", None)

    # Последний отчет (через reports_db)
    # Нам нужно имя пользователя системы, а не Telegram Name
    # Лучше брать из state, если мы его там храним при логине.
    # Пока используем callback.from_user.username как заглушку или имя из БД
    # В идеале: active_user = await accountant_db.get_active_username(...)
    # Но для упрощения пока оставим user_name

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

    # Клавиатура препаратов (передаем pharmacy_db)
    keyboard = await get_prep_inline(pharmacy_db, state, prefix="doc")

    await callback.message.edit_text(
        f"{report_text}👨‍⚕️ <b>{doc_name}</b>\n💊 Выберите препараты:",
        reply_markup=keyboard
    )
    await callback.answer()


# ============================================================
# ✅ ПОДТВЕРЖДЕНИЕ ВЫБОРА
# ============================================================
@router.callback_query(F.data == "confirm_selection", PrescriptionFSM.choose_meds)
async def confirm_selection(callback: types.CallbackQuery, state: FSMContext, pharmacy_db: BotDB):
    selected_ids = await TempDataManager.get(state, "selected_items", [])

    # Загружаем карту имен (на всякий случай обновляем)
    await load_items(state, pharmacy_db)
    prep_map = await TempDataManager.get(state, "prep_map", {})

    if not selected_ids:
        await callback.answer("⚠️ Вы ничего не выбрали!", show_alert=True)
        return

    prefix = await TempDataManager.get(state, "prefix")
    logger.info(f"Selection confirmed: {selected_ids}")

    # --- ВРАЧ ---
    if prefix == "doc":
        selected_names = []
        for i in selected_ids:
            # Приводим к int для поиска в словаре
            name = prep_map.get(int(i)) or prep_map.get(str(i)) or f"ID {i}"
            selected_names.append(name)

        formatted_list = "\n".join(f"• {name}" for name in selected_names)

        response_text = (
            f"✅ <b>Список сохранён:</b>\n{formatted_list}\n\n"
            "✍️ <b>Введите условия договора</b> (например: 10% скидка):"
        )
        await callback.message.edit_text(response_text)
        await state.set_state(PrescriptionFSM.contract_terms)

        # Чистим временные данные, чтобы не занимать память
        await TempDataManager.remove(state, "prep_items", "prep_map")

    # --- АПТЕКА ---
    elif prefix == "apt":
        await TempDataManager.set(state, "quantity_queue", list(selected_ids))
        await TempDataManager.set(state, "final_quantities", {})
        await TempDataManager.set(state, "prefix", "apt")

        await callback.message.edit_text("✅ <b>Список принят.</b>\nПереходим к вводу количества.")
        # Запускаем цикл опроса (передаем message объект для ответа)
        await ask_next_pharmacy_item(callback.message, state)

    else:
        await callback.answer("⚠️ Ошибка состояния", show_alert=True)


# ============================================================
# 🔢 АПТЕКА: ВВОД КОЛИЧЕСТВА (HELPER)
# ============================================================
async def ask_next_pharmacy_item(message: types.Message, state: FSMContext):
    queue = await TempDataManager.get(state, "quantity_queue", [])
    prep_map = await TempDataManager.get(state, "prep_map", {})

    # --- 🏁 ОЧЕРЕДЬ ПУСТА (Все заполнено) ---
    if not queue:
        final_quantities = await TempDataManager.get(state, "final_quantities", {})

        summary_text = "<b>✅ Данные приняты:</b>\n\n"
        for p_id, val_dict in final_quantities.items():
            # Ищем имя (как int так и str)
            name = prep_map.get(int(p_id)) or prep_map.get(str(p_id)) or "Unknown"
            req = val_dict.get('req', 0)
            rem = val_dict.get('rem', 0)
            summary_text += f"• {name}\n   └ Заявка: {req} | Остаток: {rem}\n"

        await message.answer(summary_text)

        await message.answer("✍️ <b>Напишите комментарий</b> (или отправьте '-', если нет):")
        # Исправил состояние: теперь оно ведет к message handler'у
        await state.set_state(PrescriptionFSM.pharmacy_comments)
        return

    # --- 🔄 СЛЕДУЮЩИЙ ---
    current_id = queue[0]
    current_name = prep_map.get(int(current_id)) or prep_map.get(str(current_id)) or f"ID {current_id}"

    await TempDataManager.set(state, "current_process_id", current_id)
    await TempDataManager.set(state, "current_process_name", current_name)

    await message.answer(
        f"💊 Препарат: <b>{current_name}</b>\n\n"
        f"1️⃣ Введите количество для <b>Заявки</b> (сколько заказать):"
    )
    await state.set_state(PrescriptionFSM.waiting_for_req_qty)


# ============================================================
# 🔢 АПТЕКА: ОБРАБОТЧИКИ ВВОДА
# ============================================================
@router.message(PrescriptionFSM.waiting_for_req_qty)
async def process_req_qty(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("⚠️ Пожалуйста, введите целое число для заявки.")
        return

    qty_req = int(message.text)
    await TempDataManager.set(state, "temp_req_qty", qty_req)

    med_name = await TempDataManager.get(state, "current_process_name")
    await message.answer(
        f"✅ Заявка: {qty_req}\n\n"
        f"2️⃣ Теперь введите <b>Остаток</b> (для {med_name}):"
    )
    await state.set_state(PrescriptionFSM.waiting_for_rem_qty)


@router.message(PrescriptionFSM.waiting_for_rem_qty)
async def process_rem_qty(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("⚠️ Пожалуйста, введите целое число.")
        return

    qty_rem = int(message.text)
    qty_req = await TempDataManager.get(state, "temp_req_qty")
    current_id = await TempDataManager.get(state, "current_process_id")

    # Сохраняем пару значений
    value_data = {"req": qty_req, "rem": qty_rem}

    final_quantities = await TempDataManager.get(state, "final_quantities", {})
    final_quantities[str(current_id)] = value_data  # Используем str ключ для JSON-сериализации
    await TempDataManager.set(state, "final_quantities", final_quantities)

    # Удаляем обработанный элемент из очереди
    queue = await TempDataManager.get(state, "quantity_queue", [])
    if queue:
        queue.pop(0)
    await TempDataManager.set(state, "quantity_queue", queue)

    # Переходим к следующему
    await ask_next_pharmacy_item(message, state)


@router.message(PrescriptionFSM.pharmacy_comments)
async def process_pharmacy_comment(message: types.Message, state: FSMContext):
    comment = message.text.strip()
    if comment.lower() in ["-", "нет", "no"]:
        comment = ""

    await TempDataManager.set(state, "comms", comment)

    # Кнопка "Посмотреть"
    kb = get_confirm_inline(mode=True)  # Используем helper для кнопки

    await state.set_state(PrescriptionFSM.confirmation)
    await message.answer("✅ Данные готовы. Нажмите кнопку ниже для проверки:", reply_markup=kb)


# ============================================================
# 📄 ПАГИНАЦИЯ ВРАЧЕЙ
# ============================================================
@router.callback_query(F.data.startswith("docpage_"))
async def paginate_doctors(callback: types.CallbackQuery, state: FSMContext, pharmacy_db: BotDB):
    try:
        parts = callback.data.split("_")
        lpu_id = int(parts[1])
        page = int(parts[2])

        # Передаем pharmacy_db!
        keyboard = await get_doctors_inline(pharmacy_db, state, lpu_id=lpu_id, page=page)

        with suppress(TelegramBadRequest):
            await callback.message.edit_reply_markup(reply_markup=keyboard)

    except Exception as e:
        logger.error(f"Pagination error: {e}")
    await callback.answer()