from aiogram import Router, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

# Импорты ваших клавиатур и состояний
# from states.main_menu_states import MainMenu
from keyboard.inline.menu_kb import get_main_menu_inline, get_guest_menu_inline

# Импорт БД (где лежат пользователи)
from loader import pharmacyDB, accountantDB

router = Router()


# ============================================================
# 🏁 ENTRY POINT: /start
# ============================================================
@router.message(Command("start"))
async def start_command(message: types.Message, state: FSMContext):
    """
    Проверяет статус пользователя:
    1. Нет в базе -> Гостевое меню (Регистрация).
    2. Есть, но is_approved=0 -> Сообщение "Ждите".
    3. Есть, is_approved=1 -> Главное меню.
    """
    user_id = message.from_user.id

    # 1. Очищаем старые состояния во избежание багов
    await state.clear()

    # 2. Проверяем статус пользователя в БД
    # Метод должен возвращать:
    # True  - если одобрен
    # False - если есть в базе, но не одобрен (0)
    # None  - если вообще нет в базе
    is_approved = await accountantDB.is_user_approved(user_id)

    # --- СЦЕНАРИЙ 1: ПОЛЬЗОВАТЕЛЬ ОДОБРЕН ---
    if is_approved is True:
        # await state.set_state(MainMenu.logged_in)

        # Получаем имя для приветствия (если нужно)
        username = await accountantDB.get_active_username(user_id) or message.from_user.first_name

        # ⚠️ Не забываем await, так как меню теперь проверяет задачи!
        kb = await get_main_menu_inline(user_id)

        await message.answer(
            f"👋 С возвращением, <b>{username}</b>!\n\n"
            "Выберите раздел в меню ниже:",
            reply_markup=kb
        )

    # --- СЦЕНАРИЙ 2: ЖДЕТ ПОДТВЕРЖДЕНИЯ ---
    elif is_approved is False:
        # Можно не ставить состояние или поставить какое-то нейтральное
        # await state.set_state(MainMenu.main)

        await message.answer(
            "⏳ <b>Ваш аккаунт ожидает проверки.</b>\n\n"
            "Администратор еще не подтвердил вашу регистрацию.\n"
            "Как только доступ будет открыт, вы получите уведомление."
        )

    # --- СЦЕНАРИЙ 3: НЕ ЗАРЕГИСТРИРОВАН ---
    else:
        # await state.set_state(MainMenu.main)

        await message.answer(
            "👋 Приветствую! Это бот <b>AnovaPharm</b>.\n\n"
            "Для начала работы необходимо зарегистрироваться и войти в систему.",
            reply_markup=get_guest_menu_inline()
        )