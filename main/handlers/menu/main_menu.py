from aiogram import Router, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import ReplyKeyboardRemove

from loader import accountantDB

from states.menu.main_menu_state import MainMenu
from states.menu.register_state import Register

from filters.is_logged_in import IsLoggedInFilter

from utils.ui.ui_helper import send_inline_menu

from keyboard.reply import reply_buttons
from keyboard.inline import inline_buttons

router = Router()


# === Команда /start ===
@router.message(Command("start"))
async def start(message: types.Message, state: FSMContext):
    await state.set_state(MainMenu.main)
    await message.answer(
        "Приветствую, это бот AnovaPharm! 👋",
        reply_markup=reply_buttons.get_main_kb()
    )


# === Пользовательская часть ===
@router.message(F.text == "🧑‍⚕️ Пользователь")
async def user_entry(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    data = await state.get_data()
    user_name = data.get("username")

    # --- ASYNC вызовы БД ---
    exists = await accountantDB.user_exists(user_id)
    logged_in = await accountantDB.is_logged_in(user_id, user_name)

    if exists and logged_in:
        await message.answer(
            f"С возвращением, {user_name}! 👋",
            reply_markup=ReplyKeyboardRemove()
        )

        await message.answer(
            "Выберите действие:",
            reply_markup=inline_buttons.get_users_inline()
        )

        await state.set_state(MainMenu.logged_in)

    else:
        await message.answer(
            "👋 Похоже, вы новый пользователь.\nХотите зарегистрироваться?",
            reply_markup=reply_buttons.get_yn_kb()
        )
        await state.set_state(Register.begin)


# === Админ панель ===
@router.message(IsLoggedInFilter(), MainMenu.logged_in, F.text == "🏥 Адм. панель")
async def admin_panel(message: types.Message, state: FSMContext):
    await message.answer("Админ панель ⚙️", reply_markup=ReplyKeyboardRemove())
    await message.answer("Выберите действие:", reply_markup=inline_buttons.get_admin_inline())


# === Отзывы ===
@router.message(IsLoggedInFilter(), MainMenu.logged_in, F.text == "💊 Отзывы")
async def feedback_menu(message: types.Message):
    await message.answer("Отзывы 💬", reply_markup=ReplyKeyboardRemove())
    await message.answer("Выберите действие:", reply_markup=inline_buttons.get_feedback_inline())


# === Отчёты ===
@router.message(IsLoggedInFilter(), MainMenu.logged_in, F.text == "📊 Отчёт")
async def reports_logged_in(message: types.Message):
    await message.answer("Отчёты 📊", reply_markup=ReplyKeyboardRemove())
    await message.answer("Выберите тип отчёта:", reply_markup=inline_buttons.get_reports_inline())


# Если пользователь не авторизован
restricted_buttons = ['🏥 Адм. панель', '💊 Отзывы', '📊 Отчёт']

@router.message(MainMenu.main, F.text.in_(restricted_buttons))
async def reports_no_auth(message: types.Message):
    await message.answer("⛔ Сначала войдите в систему через '🧑‍⚕️ Пользователь'.")


# # === Вернуться в меню ===
# @router.message(F.text == "🔙 Меню")
# async def back_to_main(message: types.Message, state: FSMContext):
#     user_id = message.from_user.id
#     user_name = message.from_user.username
#     logged_in = await accountantDB.is_logged_in(user_id, user_name)
#
#     if logged_in:
#         await state.set_state(MainMenu.logged_in)
#     else:
#         await state.set_state(MainMenu.main)
#
#     await message.answer(
#         "Главное меню:",
#         reply_markup=reply_buttons.get_main_kb()
#     )
#

# === Выход из аккаунта ===
@router.message(MainMenu.logged_in, F.text == "🚪 Выйти из уч. записи")
async def logout(message: types.Message, state: FSMContext):
    user_id = message.from_user.id

    # ASYNC logout
    await accountantDB.logout_user(user_id)

    await state.set_state(MainMenu.main)

    await message.answer(
        "Вы вышли из учётной записи 👋",
        reply_markup=reply_buttons.get_main_kb()
    )
