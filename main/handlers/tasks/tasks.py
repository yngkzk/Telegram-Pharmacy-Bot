from aiogram import Router, F, types
from aiogram.types import CallbackQuery

from loader import reportsDB
from keyboard.inline.menu_kb import get_main_menu_inline

router = Router()


@router.callback_query(F.data == "show_tasks")
async def show_user_tasks(callback: types.CallbackQuery):
    """
    Показывает список задач пользователю и отмечает их как прочитанные.
    """
    user_id = callback.from_user.id

    # 1. Получаем список активных задач из БД
    tasks = await reportsDB.get_active_tasks()

    # Если задач нет
    if not tasks:
        await callback.answer("🎉 Задач пока нет, отдыхайте!", show_alert=True)
        # На всякий случай обновляем меню (вдруг там висел старый индикатор)
        new_menu = await get_main_menu_inline(user_id)
        try:
            await callback.message.edit_reply_markup(reply_markup=new_menu)
        except:
            pass
        return

    # 2. Формируем красивый текст
    text = "📋 <b>АКТУАЛЬНЫЕ ЗАДАЧИ ОТ РУКОВОДСТВА:</b>\n\n"
    for idx, task in enumerate(tasks, 1):
        # task['text'] - текст задачи
        # task['created_at'] - дата (если нужно)
        text += f"🔹 <b>Задача №{idx}</b>\n{task['text']}\n➖➖➖➖➖➖\n"

    # 3. Самое важное: Отмечаем, что юзер это прочитал
    # (В следующий раз кнопка будет без "!!")
    await reportsDB.mark_all_as_read(user_id)

    # 4. Обновляем меню (чтобы убрать восклицательные знаки прямо сейчас)
    new_menu = await get_main_menu_inline(user_id)

    # Отправляем задачи новым сообщением или редактируем текущее (как вам удобнее)
    # Вариант А: Редактировать текущее (заменит меню на текст задач)
    # await callback.message.edit_text(text, reply_markup=new_menu)

    # Вариант Б (Лучше): Отправить задачи новым сообщением, а меню обновить внизу
    await callback.message.answer(text)

    # Просто обновляем клавиатуру на сообщении, где нажали кнопку (убираем !!)
    try:
        await callback.message.edit_reply_markup(reply_markup=new_menu)
    except Exception:
        pass  # Если ничего не изменилось, телеграм выдаст ошибку, игнорируем

    await callback.answer()