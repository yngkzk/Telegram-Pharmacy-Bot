from aiogram import types, Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import ReplyKeyboardRemove

from states.register_state import Register, LoginFSM
from states.main_menu_state import MainMenu

from loader import accountantDB

from utils.pw import hash_password
from keyboard import reply_buttons, inline_buttons

router = Router()

# Старт регистрации
@router.message(F.text == "Да ✅")
async def start_register(message: types.Message, state: FSMContext):
    await message.answer("Введите регион:", reply_markup=reply_buttons.get_region_kb())
    await state.set_state(Register.region)


@router.message(F.text == "Да ✅")
async def already_started(message: types.Message, state: FSMContext):
    """
    Если пользователь снова нажал "Да ✅" не на том шаге — подсказываем, что делать.
    """
    current_state = await state.get_state()
    texts = {
        'Register:login': 'логин',
        'Register:region': 'регион',
        'Register:password': 'пароль',
        'Register:confirm': 'пароль заново'
    }
    text = texts.get(current_state, 'сначала отправь /start')

    await message.answer(
        f"Вы уже начал регистрацию, введи {text}.",
        reply_markup=types.ReplyKeyboardRemove()
    )


# === Отказ регистрации ===
@router.message(F.text == "Нет ❌")
async def reject_registration(message: types.Message, state: FSMContext):
    await message.answer("Выберите пользователя:", reply_markup=reply_buttons.get_users_kb())
    await state.set_state(LoginFSM.choose_user)

# === ПОЛЬЗОВАТЕЛЬ, КОТОРЫЙ УЖЕ НАХОДИТСЯ В БД ===
@router.message(LoginFSM.choose_user)
async def user_chosen(message: types.Message, state: FSMContext):
    text = message.text

    # Если нажали "Меню"
    if text == "🔙 Меню":
        from states.main_menu_state import MainMenu
        await state.set_state(MainMenu.main)
        await message.answer(
            "Возвращаемся в главное меню.",
            reply_markup=reply_buttons.get_main_kb()
        )
        return

    # Проверяем выбранного пользователя
    users = accountantDB.get_user_list()
    if text not in users:
        await message.answer("⚠️ Такого пользователя нет. Попробуйте снова.")
        return

    # Сохраняем выбранного пользователя и просим пароль
    await state.update_data(username=text)
    await message.answer(f"Введите пароль для пользователя <b>{text}</b> 🔑", parse_mode="HTML", reply_markup=ReplyKeyboardRemove())
    await state.set_state(LoginFSM.enter_password)


@router.message(LoginFSM.enter_password)
async def check_password(message: types.Message, state: FSMContext):
    password = message.text
    data = await state.get_data()
    username = data.get("username")

    if accountantDB.check_password(username, password):
        await message.answer(f"✅ Добро пожаловать, {username}!", reply_markup=ReplyKeyboardRemove())
        await message.answer("Выберите действие:", reply_markup=inline_buttons.get_users_inline())
        accountantDB.set_logged_in(username, True)
        await state.set_state(MainMenu.logged_in)
    else:
        await message.answer("❌ Неверный пароль. Попробуйте снова.")




# === Отмена регистрации ===
@router.message(F.text == "Отменить 🚫")
async def cancel(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("❌ Регистрация отменена. Вы можете начать заново командой /start", reply_markup=ReplyKeyboardRemove())


# Регион
@router.message(Register.region)
async def get_region(message: types.Message, state: FSMContext):
    await state.update_data(region=message.text)
    await message.answer("Введите логин:", reply_markup=reply_buttons.get_cancel_kb())
    await state.set_state(Register.login)


# Логин
@router.message(Register.login)
async def get_login(message: types.Message, state: FSMContext):
    await state.update_data(login=message.text)
    await message.answer("Введите пароль:")
    await state.set_state(Register.password)


# Пароль
@router.message(Register.password)
async def get_password(message: types.Message, state: FSMContext):
    await state.update_data(password=message.text)
    await message.answer("Повторите пароль для подтверждения:")
    await state.set_state(Register.confirm)


# Подтверждение
@router.message(Register.confirm)
async def confirm_password(message: types.Message, state: FSMContext):
    data = await state.get_data()
    if message.text != data["password"]:
        await message.answer("❌ Пароли не совпадают, введите заново пароль.")
        await state.set_state(Register.password)
        return

    user_id = message.from_user.id
    user_name = data["login"]
    user_password = data["password"]
    region = data["region"]

    hashed_pw = hash_password(user_password)

    await message.answer(f"✅ Регистрация завершена!\nЛогин: {user_name}", reply_markup=reply_buttons.get_main_kb())
    accountantDB.add_user(user_id, user_name, hashed_pw, region)
    await state.set(MainMenu.main)