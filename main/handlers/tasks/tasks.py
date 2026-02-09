from aiogram import Router, F, types
from aiogram.types import CallbackQuery

# 1. Импортируем класс базы (для аннотации типов)
from db.reports import ReportRepository

# 2. Импортируем генератор меню
from keyboard.inline.menu_kb import get_main_menu_inline

router = Router()


@router.callback_query(F.data == "show_tasks")
async def show_user_tasks(
        callback: types.CallbackQuery,
        reports_db: ReportRepository  # <-- Внедряем зависимость
):
    """
    Показывает список задач пользователю и отмечает их как прочитанные.
    """
    user_id = callback.from_user.id

    # 1. Получаем список активных задач из БД (через объект, а не глобальную переменную)
    tasks = await reports_db.get_active_tasks()

    # Если задач нет
    if not tasks:
        await callback.answer("🎉 Задач пока нет, отдыхайте!", show_alert=True)

        # Обновляем меню (передаем reports_db!)
        new_menu = await get_main_menu_inline(user_id, reports_db)
        try:
            await callback.message.edit_reply_markup(reply_markup=new_menu)
        except:
            pass
        return

    # 2. Формируем красивый текст
    text = "📋 <b>АКТУАЛЬНЫЕ ЗАДАЧИ ОТ РУКОВОДСТВА:</b>\n\n"

    # task - это объект aiosqlite.Row, к нему можно обращаться как к словарю
    for idx, task in enumerate(tasks, 1):
        task_text = task['text']
        # task_date = task['created_at'] # Если нужно вывести дату
        text += f"🔹 <b>Задача №{idx}</b>\n{task_text}\n➖➖➖➖➖➖\n"

    # 3. Самое важное: Отмечаем, что юзер это прочитал
    await reports_db.mark_all_as_read(user_id)

    # 4. Обновляем меню (чтобы убрать восклицательные знаки !!)
    # ВАЖНО: Передаем reports_db в функцию меню
    new_menu = await get_main_menu_inline(user_id, reports_db)

    # Отправляем задачи новым сообщением
    await callback.message.answer(text)

    # Обновляем клавиатуру на старом сообщении (где нажали кнопку)
    try:
        await callback.message.edit_reply_markup(reply_markup=new_menu)
    except Exception:
        pass

    await callback.answer()