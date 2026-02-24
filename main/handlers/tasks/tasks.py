from aiogram import Router, F, types

# 🔥 НОВЫЙ ИМПОРТ РЕПОЗИТОРИЯ
from infrastructure.database.repo.report_repo import ReportRepository

# Импортируем генератор меню
from keyboard.inline.menu_kb import get_main_menu_inline

router = Router()


@router.callback_query(F.data == "show_tasks")
async def show_user_tasks(
        callback: types.CallbackQuery,
        reports_db: ReportRepository  # <-- Внедрено через Middleware!
):
    """
    Показывает список задач пользователю и отмечает их как прочитанные.
    """
    user_id = callback.from_user.id

    # 1. Получаем список активных задач из новой БД
    tasks = await reports_db.get_active_tasks()

    # Если задач нет
    if not tasks:
        await callback.answer("🎉 Задач пока нет, отдыхайте!", show_alert=True)

        # Обновляем меню (передаем reports_db!)
        new_menu = await get_main_menu_inline(user_id, reports_db)
        try:
            await callback.message.edit_reply_markup(reply_markup=new_menu)
        except Exception:
            pass
        return

    # 2. Формируем красивый текст
    text = "📋 <b>АКТУАЛЬНЫЕ ЗАДАЧИ ОТ РУКОВОДСТВА:</b>\n\n"

    # Теперь task - это обычный словарь, который нам вернул новый репозиторий
    for idx, task in enumerate(tasks, 1):
        task_text = task.get('text', 'Пустая задача')
        # Если нужно вывести дату:
        # task_date = task.get('created_at').strftime("%d.%m.%Y") if task.get('created_at') else ""
        text += f"🔹 <b>Задача №{idx}</b>\n{task_text}\n➖➖➖➖➖➖\n"

    # 3. Самое важное: Отмечаем, что юзер это прочитал
    await reports_db.mark_all_as_read(user_id)

    # 4. Обновляем меню (чтобы убрать восклицательные знаки !!)
    new_menu = await get_main_menu_inline(user_id, reports_db)

    # Отправляем задачи новым сообщением
    await callback.message.answer(text)

    # Обновляем клавиатуру на старом сообщении (где нажали кнопку)
    try:
        await callback.message.edit_reply_markup(reply_markup=new_menu)
    except Exception:
        pass

    await callback.answer()