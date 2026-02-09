from aiogram import Router, F, types
from aiogram.types import BufferedInputFile, CallbackQuery
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from datetime import datetime, timedelta

# 1. Импорты баз данных (Типы)
from db.database import BotDB
from db.reports import ReportRepository

# 2. Утилиты и логирование
from utils.report.excel_generator import create_excel_report
from utils.logger.logger_config import logger

# 3. Клавиатуры и состояния
from keyboard.inline.admin_kb import get_admin_menu, get_report_period_kb, get_report_users_kb
from keyboard.inline.menu_kb import get_main_menu_inline
from states.admin.report_states import AdminReportFSM

router = Router()


class AdminTaskFSM(StatesGroup):
    waiting_for_task_text = State()


# ============================================================
# 📝 СОЗДАНИЕ ЗАДАЧИ
# ============================================================
@router.callback_query(F.data == "admin_create_task")
async def admin_start_task(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("✍️ Введите текст новой задачи для всех сотрудников:")
    await state.set_state(AdminTaskFSM.waiting_for_task_text)
    await callback.answer()


@router.message(AdminTaskFSM.waiting_for_task_text)
async def admin_save_task(message: types.Message, state: FSMContext, reports_db: ReportRepository):
    text = message.text

    # Используем reports_db из аргументов
    await reports_db.add_task(text)

    await message.answer(f"✅ Задача опубликована:\n\n<i>{text}</i>", reply_markup=get_admin_menu())
    await state.clear()


# ============================================================
# 📊 EXPORT FLOW (ВЫГРУЗКА ОТЧЕТОВ)
# ============================================================

# 1. Старт: Выбор периода
@router.callback_query(F.data == "admin_export_start")
async def start_export_flow(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(AdminReportFSM.choose_period)
    await callback.message.edit_text(
        "📊 <b>Выгрузка отчетов</b>\n\nВыберите период:",
        reply_markup=get_report_period_kb()
    )
    await callback.answer()


# 2. Обработка выбора периода -> Выбор сотрудника
@router.callback_query(AdminReportFSM.choose_period, F.data.startswith("period_"))
async def process_period(callback: types.CallbackQuery, state: FSMContext, accountant_db: BotDB):
    mode = callback.data.split("_")[1]

    today = datetime.now().date()
    start_date = today
    end_date = today

    if mode == "today":
        start_date = today
        end_date = today
    elif mode == "yesterday":
        start_date = today - timedelta(days=1)
        end_date = start_date
    elif mode == "week":
        start_date = today - timedelta(days=today.weekday())  # Понедельник
        end_date = today
    elif mode == "month":
        start_date = today.replace(day=1)
        end_date = today

    # Сохраняем даты
    await state.update_data(start_date=str(start_date), end_date=str(end_date))

    # Переходим к выбору сотрудника
    await state.set_state(AdminReportFSM.choose_employee)

    # Получаем список сотрудников через accountant_db
    users = await accountant_db.get_user_list()

    await callback.message.edit_text(
        f"✅ Период: <b>{start_date} — {end_date}</b>\n\nТеперь выберите сотрудника:",
        reply_markup=get_report_users_kb(users)
    )
    await callback.answer()


# 3. Обработка выбора сотрудника -> ГЕНЕРАЦИЯ EXCEL
@router.callback_query(AdminReportFSM.choose_employee, F.data.startswith("user_filter_"))
async def process_user_and_generate(
        callback: types.CallbackQuery,
        state: FSMContext,
        reports_db: ReportRepository
):
    selected_user = callback.data.split("user_filter_")[1]  # 'all' или 'Ivan'

    data = await state.get_data()
    start_date = data.get('start_date')
    end_date = data.get('end_date')

    await callback.message.edit_text(
        f"⏳ <b>Формирую отчет...</b>\n"
        f"📅 {start_date} — {end_date}\n"
        f"👤 Сотрудник: {selected_user}\n"
        "Пожалуйста, подождите."
    )

    try:
        # Используем reports_db для получения данных
        doc_data = await reports_db.fetch_filtered_doctor_data(start_date, end_date, selected_user)
        apt_data = await reports_db.fetch_filtered_apothecary_data(start_date, end_date, selected_user)

        if not doc_data and not apt_data:
            await callback.message.edit_text(
                "❌ <b>За выбранный период данных нет.</b>",
                reply_markup=get_admin_menu()
            )
            await state.clear()
            return

        # Генерация Excel
        excel_file = create_excel_report(doc_data, apt_data)

        # Имя файла
        filename = f"Report_{start_date}_to_{end_date}.xlsx"
        if selected_user != "all":
            filename = f"Report_{selected_user}_{start_date}.xlsx"

        file_to_send = BufferedInputFile(excel_file.read(), filename=filename)

        await callback.message.answer_document(
            document=file_to_send,
            caption=(
                f"📊 <b>Готовый отчет</b>\n"
                f"📅 Период: {start_date} — {end_date}\n"
                f"👤 Фильтр: {selected_user}"
            )
        )

        # Возврат в меню
        await callback.message.answer("Админ-панель:", reply_markup=get_admin_menu())
        # Удаляем сообщение "Формирую..."
        try:
            await callback.message.delete()
        except:
            pass

    except Exception as e:
        logger.error(f"Export Error: {e}")
        await callback.message.answer(f"❌ Ошибка при экспорте: {e}", reply_markup=get_admin_menu())

    await state.clear()


# Отмена действий админа
@router.callback_query(F.data == "admin_cancel")
async def admin_cancel(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("⚙️ Админ панель", reply_markup=get_admin_menu())


# ============================================================
# 👥 СПИСОК НОВЫХ ЗАЯВОК (Pending Users)
# ============================================================
@router.callback_query(F.data == "admin_users_list")
async def show_pending_users(callback: CallbackQuery, accountant_db: BotDB):
    # Используем accountant_db
    pending_users = await accountant_db.get_pending_users()

    if not pending_users:
        await callback.answer("✅ Новых заявок нет.", show_alert=True)
        return

    builder = InlineKeyboardBuilder()
    text = "👤 <b>Заявки на регистрацию:</b>\n\n"

    for user in pending_users:
        u_id = user['user_id']
        name = user['user_name']
        region = user['region']
        text += f"▪️ {name} ({region})\n"

        builder.button(text=f"✅ {name}", callback_data=f"decision_approve_{u_id}")
        builder.button(text="❌ Откл.", callback_data=f"decision_reject_{u_id}")

    builder.button(text="🔙 Назад", callback_data="admin_panel")
    builder.adjust(2, 2)

    await callback.message.edit_text(text, reply_markup=builder.as_markup())
    await callback.answer()


# ============================================================
# ✅ ОБРАБОТКА РЕШЕНИЯ (Принять / Отклонить)
# ============================================================
@router.callback_query(F.data.startswith("decision_"))
async def process_user_decision(
        callback: CallbackQuery,
        accountant_db: BotDB,
        reports_db: ReportRepository
):
    try:
        # decision_approve_12345
        action, user_id_str = callback.data.split("_")[1], callback.data.split("_")[2]
        target_user_id = int(user_id_str)
    except Exception:
        await callback.answer("Ошибка данных")
        return

    if action == "approve":
        # 1. Обновляем статус
        await accountant_db.approve_user(target_user_id)
        await callback.answer("✅ Пользователь допущен!")

        # 2. Уведомляем пользователя
        try:
            # ⚠️ ВАЖНО: передаем reports_db, так как меню проверяет задачи
            user_kb = await get_main_menu_inline(target_user_id, reports_db)

            await callback.bot.send_message(
                target_user_id,
                "🎉 <b>Ваш аккаунт подтвержден!</b>\nДобро пожаловать в систему.",
                reply_markup=user_kb
            )
            await callback.message.answer(f"✅ Пользователь {target_user_id} уведомлен.", reply_markup=get_admin_menu())
        except Exception as e:
            logger.error(f"Не удалось отправить уведомление юзеру {target_user_id}: {e}")
            await callback.message.answer("⚠️ Пользователь одобрен, но личное сообщение не отправлено.")

    elif action == "reject":
        # 1. Удаляем
        await accountant_db.delete_user(target_user_id)
        await callback.answer("❌ Заявка отклонена.")

        # 2. Уведомляем
        try:
            await callback.bot.send_message(
                target_user_id,
                "😔 Ваша заявка на регистрацию была отклонена администратором."
            )
        except:
            pass

    # Обновляем список (рекурсия)
    await show_pending_users(callback, accountant_db)