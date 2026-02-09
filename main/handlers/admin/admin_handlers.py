from aiogram import Router, F, types
from aiogram.types import BufferedInputFile, CallbackQuery
from datetime import datetime
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder

# Import your database and the Excel generator we created earlier
from loader import reportsDB, accountantDB
from utils.report.excel_generator import create_excel_report
from keyboard.inline.admin_kb import get_admin_menu

router = Router()


class AdminTaskFSM(StatesGroup):
    waiting_for_task_text = State()


# 1. Кнопка в админке "Создать задачу"
@router.callback_query(F.data == "admin_create_task")
async def admin_start_task(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("✍️ Введите текст новой задачи для всех сотрудников:")
    await state.set_state(AdminTaskFSM.waiting_for_task_text)
    await callback.answer()

# 2. Сохранение
@router.message(AdminTaskFSM.waiting_for_task_text)
async def admin_save_task(message: types.Message, state: FSMContext):
    text = message.text

    # Сохраняем в БД
    await reportsDB.add_task(text)

    await message.answer(f"✅ Задача опубликована:\n\n<i>{text}</i>")
    await state.clear()

# ============================================================
# 📊 ADMIN: EXPORT EXCEL
# ============================================================
@router.callback_query(F.data == "admin_export_xlsx")
async def admin_export_reports(callback: types.CallbackQuery):
    """Generates and sends the full Excel report to the admin."""

    # 1. Notify admin process started (Edit text to avoid multiple clicks)
    await callback.message.edit_text(
        "⏳ <b>Формирую таблицу...</b>\nПожалуйста, подождите, это может занять несколько секунд.")

    try:
        # 2. Fetch All Data (Doctors + Pharmacies)
        doc_data = await reportsDB.fetch_all_doctor_data()
        apt_data = await reportsDB.fetch_all_apothecary_data()

        if not doc_data and not apt_data:
            await callback.message.edit_text(
                "❌ <b>База данных пуста.</b>\nНет отчетов для экспорта.",
                reply_markup=get_admin_menu()
            )
            return

        # 3. Generate Excel File (in memory)
        excel_file = create_excel_report(doc_data, apt_data)

        # 4. Prepare Filename
        date_str = datetime.now().strftime("%Y-%m-%d_%H-%M")
        filename = f"Full_Report_{date_str}.xlsx"

        # 5. Send the File
        file_to_send = BufferedInputFile(excel_file.read(), filename=filename)

        # Send as a new message (document)
        await callback.message.answer_document(
            document=file_to_send,
            caption=f"📊 <b>Сводный отчет (Excel)</b>\n📅 Дата: {datetime.now().strftime('%d.%m.%Y %H:%M')}"
        )

        # 6. Restore Admin Menu
        await callback.message.answer("Главное меню администратора:", reply_markup=get_admin_menu())

        # Delete the "Processing..." message
        await callback.message.delete()

    except Exception as e:
        # Log error and notify admin
        print(f"Export Error: {e}")
        await callback.message.answer(f"❌ <b>Ошибка при создании отчета:</b>\n{e}", reply_markup=get_admin_menu())

    await callback.answer()


# ============================================================
# 👥 СПИСОК НОВЫХ ЗАЯВОК (Pending Users)
# ============================================================
@router.callback_query(F.data == "admin_users_list")
async def show_pending_users(callback: CallbackQuery):
    # 1. Получаем список из БД
    pending_users = await accountantDB.get_pending_users()

    if not pending_users:
        await callback.answer("✅ Новых заявок нет.", show_alert=True)
        return

    # 2. Строим список кнопок
    builder = InlineKeyboardBuilder()

    text = "👤 <b>Заявки на регистрацию:</b>\n\n"

    for user in pending_users:
        u_id = user['user_id']
        name = user['user_name']
        region = user['region']

        text += f"▪️ {name} ({region})\n"

        # Кнопки ДА/НЕТ для каждого юзера
        # Формат callback: "decision_approve_12345"
        builder.button(text=f"✅ {name}", callback_data=f"decision_approve_{u_id}")
        builder.button(text="❌ Откл.", callback_data=f"decision_reject_{u_id}")

    builder.button(text="🔙 Назад", callback_data="admin_panel")
    builder.adjust(2, 2)  # По 2 кнопки в ряд (Принять / Отклонить)

    await callback.message.edit_text(text, reply_markup=builder.as_markup())
    await callback.answer()


# ============================================================
# ✅ ОБРАБОТКА РЕШЕНИЯ (Принять / Отклонить)
# ============================================================
@router.callback_query(F.data.startswith("decision_"))
async def process_user_decision(callback: CallbackQuery):
    action, user_id_str = callback.data.split("_")[1], callback.data.split("_")[2]
    target_user_id = int(user_id_str)

    if action == "approve":
        # 1. Обновляем статус в БД
        await accountantDB.approve_user(target_user_id)

        # 2. Уведомляем админа
        await callback.answer("✅ Пользователь допущен!")

        # 3. Уведомляем ПОЛЬЗОВАТЕЛЯ (Самое важное!)
        try:
            from keyboard.inline.menu_kb import get_main_menu_inline
            # Отправляем ему меню
            user_kb = await get_main_menu_inline(target_user_id)
            await callback.bot.send_message(
                target_user_id,
                "🎉 <b>Ваш аккаунт подтвержден!</b>\nДобро пожаловать в систему.",
                reply_markup=user_kb
            )
            admin_kb = get_admin_menu()
            await callback.message.answer(f"✅ Готово, что нибудь еще?", reply_markup=admin_kb)
        except Exception as e:
            logger.error(f"Не удалось отправить уведомление юзеру {target_user_id}: {e}")

    elif action == "reject":
        # 1. Удаляем из БД
        await accountantDB.delete_user(target_user_id)

        await callback.answer("❌ Заявка отклонена.")

        # 2. Уведомляем пользователя
        try:
            await callback.bot.send_message(target_user_id,
                                            "😔 Ваша заявка на регистрацию была отклонена администратором.")
        except:
            pass

    # Обновляем список (возвращаемся к списку заявок)
    await show_pending_users(callback)