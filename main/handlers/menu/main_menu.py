from aiogram import Router, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

# 🔥 НОВЫЕ ЧИСТЫЕ ИМПОРТЫ РЕПОЗИТОРИЕВ
from infrastructure.database.repo.user_repo import UserRepository
from infrastructure.database.repo.report_repo import ReportRepository

from keyboard.inline.menu_kb import get_main_menu_inline, get_guest_menu_inline

router = Router()

@router.message(Command("start"))
async def start_command(
        message: types.Message,
        state: FSMContext,
        user_repo: UserRepository,     # <-- Магия Middleware в действии!
        reports_db: ReportRepository   # <-- Берем из нового места
):
    user_id = message.from_user.id
    await state.clear()

    # --- SENIOR LOGIC ---
    # Получаем юзера напрямую (никаких async for session!)
    user = await user_repo.get_user(user_id)

    # Логика определения статуса
    # Если юзера нет в базе ORM -> он гость
    if not user:
        await message.answer(
            "👋 Приветствую! Это бот <b>AnovaPharm</b>.\n\n"
            "Для начала работы необходимо зарегистрироваться и войти в систему.",
            reply_markup=get_guest_menu_inline()
        )
        return

    # Если юзер есть, проверяем флаг is_approved
    if user.is_approved:
        # Получаем актуальное имя из базы
        username = user.user_name or message.from_user.first_name

        kb = await get_main_menu_inline(user_id, reports_db)
        await message.answer(
            f"👋 С возвращением, <b>{username}</b>!\n\n"
            "Выберите раздел в меню ниже:",
            reply_markup=kb
        )
    else:
        # Юзер есть, но не одобрен
        await message.answer(
            "⏳ <b>Ваш аккаунт ожидает проверки.</b>\n\n"
            "Администратор еще не подтвердил вашу регистрацию.\n"
            "Как только доступ будет открыт, вы получите уведомление."
        )