from aiogram import Router, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

from loader import accountantDB
from states.menu.main_menu_state import MainMenu

# We use the NEW Inline Keyboard file (create this next if you haven't)
from keyboard.inline.menu_kb import get_main_menu_inline, get_guest_menu_inline

router = Router()


# ============================================================
# 🏁 ENTRY POINT: /start
# ============================================================
@router.message(Command("start"))
async def start_command(message: types.Message, state: FSMContext):
    """
    The only text command in the bot.
    Checks if user is logged in and shows the appropriate INLINE menu.
    """
    user_id = message.from_user.id

    # 1. Check Database (Async)
    # We get the username if they are logged in (active session)
    active_username = await accountantDB.get_active_username(user_id)

    # 2. Clear any old state to prevent bugs
    await state.clear()

    if active_username:
        # ✅ CASE: User is Logged In
        await state.set_state(MainMenu.logged_in)

        await message.answer(
            f"👋 С возвращением, <b>{active_username}</b>!\n\n"
            "Выберите раздел в меню ниже:",
            reply_markup=get_main_menu_inline()
        )
    else:
        # 👤 CASE: Guest / Not Logged In
        await state.set_state(MainMenu.main)

        await message.answer(
            "👋 Приветствую! Это бот <b>AnovaPharm</b>.\n\n"
            "Для начала работы необходимо войти в систему.",
            reply_markup=get_guest_menu_inline()
        )