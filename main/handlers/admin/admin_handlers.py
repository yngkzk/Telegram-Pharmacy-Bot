from aiogram import Router, F, types, Bot
from aiogram.types import BufferedInputFile, CallbackQuery
from datetime import datetime
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder

# 1. Импортируем классы для типов
from db.database import BotDB
from db.reports import ReportRepository

# 2. Импорт конфига (для проверки админов, если нужно)
from utils.config.settings import config
from utils.report.excel_generator import create_excel_report
from utils.logger.logger_config import logger

# 3. Импорт клавиатур
from keyboard.inline.admin_kb import get_admin_menu
from keyboard.inline.menu_kb import get_main_menu_inline

router = Router()


# Простейший фильтр: этот роутер работает только для админов
# (Можно раскомментировать, если хочешь жесткой безопасности)
# router.message.filter(F.from_user.id.in_(config.admin_ids))
# router.callback_query.filter(F.from_user.id.in_(config.admin_ids))


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
async def admin_save_task(
        message: types.Message,
        state: FSMContext,
        reports_db: ReportRepository  # <-- Внедряем базу отчетов
):
    text = message.text

    # Сохраняем в БД через переданный объект
    await reports_db.add_task(text)

    await message.answer(f"✅ Задача опубликована:\n\n<i>{text}</i>")
    await state.clear()


# ============================================================
# 📊 ADMIN: EXPORT EXCEL
# ============================================================
@router.callback_query(F.data == "admin_export_xlsx")
async def admin_export_reports(
        callback: types.CallbackQuery,
        reports_db: ReportRepository  # <-- Внедряем базу отчетов
):
    """Generates and sends the full Excel report to the admin."""

    await callback.message.edit_text(
        "⏳ <b>Формирую таблицу...</b>\nПожалуйста, подождите, это может занять несколько секунд."
    )

    try:
        # 2. Fetch All Data (Doctors + Pharmacies)
        # Используем reports_db вместо глобальной переменной
        doc_data = await reports_db.fetch_all_doctor_data()
        apt_data = await reports_db.fetch_all_apothecary_data()

        if not doc_data and not apt_data:
            await callback.message.edit_text(
                "❌ <b>База данных пуста.</b>\nНет отчетов для экспорта.",
                reply_markup=get_admin_menu()
            )
            return

        # 3. Generate Excel File (in memory)
        # Эта функция синхронная (CPU-bound), по-хорошему её бы в executor засунуть,
        # но для начала пойдет и так.
        excel_file = create_excel_report(doc_data, apt_data)

        # 4. Prepare Filename
        date_str = datetime.now().strftime("%Y-%m-%d_%H-%M")
        filename = f"Full_Report_{date_str}.xlsx"

        # 5. Send the File
        # Важно: excel_file.read() вернет байты
        file_to_send = BufferedInputFile(excel_file.read(), filename=filename)

        await callback.message.answer_document(
            document=file_to_send,
            caption=f"📊 <b>Сводный отчет (Excel)</b>\n📅 Дата: {datetime.now().strftime('%d.%m.%Y %H:%M')}"
        )

        # 6. Restore Admin Menu
        await callback.message.answer("Главное меню администратора:", reply_markup=get_admin_menu())

        # Delete the "Processing..." message
        with DeprecationWarning:  # Просто чтобы подавить warning, можно просто удалить
            try:
                await callback.message.delete()
            except:
                pass

    except Exception as e:
        logger.error(f"Export Error: {e}")
        await callback.message.answer(f"❌ <b>Ошибка при создании отчета:</b>\n{e}", reply_markup=get_admin_menu())

    await callback.answer()


# ============================================================
# 👥 СПИСОК НОВЫХ ЗАЯВОК (Pending Users)
# ============================================================
@router.callback_query(F.data == "admin_users_list")
async def show_pending_users(
        callback: CallbackQuery,
        accountant_db: BotDB  # <-- Внедряем базу пользователей
):
    # 1. Получаем список из БД
    pending_users = await accountant_db.get_pending_users()

    if not pending_users:
        await callback.answer("✅ Новых заявок нет.", show_alert=True)
        return

    # 2. Строим список кнопок
    builder = InlineKeyboardBuilder()

    text = "👤 <b>Заявки на регистрацию:</b>\n\n"

    for user in pending_users:
        # Доступ через словарь (aiosqlite.Row ведет себя как словарь)
        u_id = user['user_id']
        name = user['user_name']
        region = user['region']

        text += f"▪️ {name} ({region})\n"

        # Кнопки ДА/НЕТ для каждого юзера
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
        accountant_db: BotDB,  # База юзеров (чтобы апрувить)
        reports_db: ReportRepository  # База отчетов (чтобы сгенерить меню для юзера)
):
    try:
        _, action, user_id_str = callback.data.split("_")
        target_user_id = int(user_id_str)
    except ValueError:
        await callback.answer("Ошибка данных кнопки")
        return

    if action == "approve":
        # 1. Обновляем статус в БД
        await accountant_db.approve_user(target_user_id)
        await callback.answer("✅ Пользователь допущен!")

        # 2. Уведомляем ПОЛЬЗОВАТЕЛЯ
        try:
            # ⚠️ ВАЖНО: Передаем reports_db, так как меню теперь показывает задачи!
            user_kb = await get_main_menu_inline(target_user_id, reports_db)

            await callback.bot.send_message(
                target_user_id,
                "🎉 <b>Ваш аккаунт подтвержден!</b>\nДобро пожаловать в систему.",
                reply_markup=user_kb
            )

            # Обновляем админское меню
            await callback.message.answer(f"✅ Пользователь {target_user_id} оповещен.", reply_markup=get_admin_menu())

        except Exception as e:
            logger.error(f"Не удалось отправить уведомление юзеру {target_user_id}: {e}")
            await callback.message.answer("✅ Допущен, но уведомление не отправлено (бот заблокирован?)")

    elif action == "reject":
        # 1. Удаляем из БД
        await accountant_db.delete_user(target_user_id)
        await callback.answer("❌ Заявка отклонена.")

        # 2. Уведомляем пользователя
        try:
            await callback.bot.send_message(
                target_user_id,
                "😔 Ваша заявка на регистрацию была отклонена администратором."
            )
        except:
            pass

    # Обновляем список (рекурсивно вызываем функцию показа)
    # Передаем accountant_db явно, так как мы вызываем функцию вручную
    await show_pending_users(callback, accountant_db)