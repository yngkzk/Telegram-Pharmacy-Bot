from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder

from states.menu.register_state import Register, LoginFSM
from states.menu.main_menu_state import MainMenu

from loader import accountantDB
from utils.text.pw import hash_password

# Импортируем готовые клавиатуры
from keyboard.inline.menu_kb import get_main_menu_inline, get_guest_menu_inline

router = Router()


# ============================================================
# 🚪 ВХОД В СИСТЕМУ (ВЫБОР: РЕГИСТРАЦИЯ ИЛИ ЛОГИН)
# ============================================================
@router.callback_query(F.data == "start_registration")
async def show_auth_choice(callback: types.CallbackQuery, state: FSMContext):
    """
    Показывает выбор: Новый пользователь или Уже есть аккаунт.
    """
    builder = InlineKeyboardBuilder()
    builder.button(text="🆕 Я новый пользователь", callback_data="auth_new")
    builder.button(text="👤 У меня есть аккаунт", callback_data="auth_existing")
    builder.button(text="❌ Отмена", callback_data="auth_cancel")
    builder.adjust(1)

    await callback.message.edit_text(
        "🔐 <b>Авторизация</b>\n\nВы впервые в системе или уже зарегистрированы?",
        reply_markup=builder.as_markup()
    )
    await callback.answer()


@router.callback_query(F.data == "auth_cancel")
async def cancel_auth(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await state.set_state(MainMenu.main)
    await callback.message.edit_text(
        "🏠 Возврат в меню гостя.",
        reply_markup=get_guest_menu_inline()
    )
    await callback.answer()


# ============================================================
# 👤 ЛОГИН (СУЩЕСТВУЮЩИЙ ПОЛЬЗОВАТЕЛЬ)
# ============================================================

@router.callback_query(F.data == "auth_existing")
async def start_login_flow(callback: types.CallbackQuery, state: FSMContext):
    """
    1. Получает список юзеров из БД.
    2. Показывает их в виде кнопок.
    """
    users = await accountantDB.get_user_list()  # Возвращает список строк ['Ivan', 'Admin']

    if not users:
        await callback.message.edit_text(
            "⚠️ В базе пока нет пользователей. Пожалуйста, зарегистрируйтесь.",
            reply_markup=get_guest_menu_inline()
        )
        return

    # Строим клавиатуру с именами пользователей
    builder = InlineKeyboardBuilder()
    for user in users:
        # callback_data="login_user_Ivan"
        builder.button(text=f"👤 {user}", callback_data=f"login_user_{user}")

    builder.button(text="🔙 Назад", callback_data="start_registration")
    builder.adjust(2)  # По 2 имени в ряд

    await state.set_state(LoginFSM.choose_user)
    await callback.message.edit_text(
        "👇 <b>Выберите свой профиль:</b>",
        reply_markup=builder.as_markup()
    )
    await callback.answer()


@router.callback_query(F.data.startswith("login_user_"), LoginFSM.choose_user)
async def user_selected(callback: types.CallbackQuery, state: FSMContext):
    """
    Пользователь выбрал своё имя.
    """
    username = callback.data.split("login_user_")[1]

    await state.update_data(username=username)
    await state.set_state(LoginFSM.enter_password)

    await callback.message.edit_text(
        f"🔑 Профиль: <b>{username}</b>\n\n"
        "✍️ Введите ваш пароль:",
        reply_markup=None  # Убираем кнопки, ждем текст
    )
    await callback.answer()


@router.message(LoginFSM.enter_password)
async def check_password(message: types.Message, state: FSMContext):
    """
    Проверка пароля.
    """
    password = message.text
    data = await state.get_data()
    username = data.get("username")
    user_id = message.from_user.id

    # Попытка удалить сообщение с паролем для безопасности
    try:
        await message.delete()
    except:
        pass

    if await accountantDB.check_password(username, password):
        # ✅ УСПЕХ
        await accountantDB.set_logged_in(user_id, username, 1)

        await state.set_state(MainMenu.logged_in)
        await message.answer(
            f"✅ Добро пожаловать, <b>{username}</b>!",
            reply_markup=get_main_menu_inline()
        )
    else:
        # ❌ ОШИБКА
        msg = await message.answer("❌ Неверный пароль. Попробуйте снова:")
        # (Опционально можно добавить кнопку отмены, если забыл пароль)


# ============================================================
# 🆕 РЕГИСТРАЦИЯ (НОВЫЙ ПОЛЬЗОВАТЕЛЬ)
# ============================================================

@router.callback_query(F.data == "auth_new")
async def start_register_flow(callback: types.CallbackQuery, state: FSMContext):
    """
    1. Спрашиваем регион.
    """
    await state.set_state(Register.region)
    await callback.message.edit_text(
        "📝 <b>Регистрация</b>\n\n"
        "Введите ваш <b>Регион</b> (например: АЛА или ЮКО):"
        # Можно добавить Inline кнопки с регионами, если их мало
    )
    await callback.answer()


@router.message(Register.region)
async def get_region(message: types.Message, state: FSMContext):
    await state.update_data(region=message.text)

    await state.set_state(Register.login)
    await message.answer("👤 Придумайте <b>Логин</b> (Имя пользователя):")


@router.message(Register.login)
async def get_login(message: types.Message, state: FSMContext):
    username = message.text

    # Проверка, занят ли логин (Опционально, если есть такой метод в БД)
    # if await accountantDB.user_exists(username): ...

    await state.update_data(login=username)

    await state.set_state(Register.password)
    await message.answer("🔑 Придумайте <b>Пароль</b>:")


@router.message(Register.password)
async def get_password(message: types.Message, state: FSMContext):
    await state.update_data(password=message.text)
    try:
        await message.delete()  # Скрываем пароль
    except:
        pass

    await state.set_state(Register.confirm)
    await message.answer("🔐 <b>Повторите пароль</b> для подтверждения:")


@router.message(Register.confirm)
async def confirm_password(message: types.Message, state: FSMContext):
    data = await state.get_data()

    try:
        await message.delete()
    except:
        pass

    if message.text != data["password"]:
        await message.answer("❌ Пароли не совпадают! Придумайте пароль заново:")
        await state.set_state(Register.password)
        return

    # --- СОХРАНЕНИЕ В БД ---
    user_id = message.from_user.id
    user_name = data["login"]
    raw_password = data["password"]
    region = data["region"]

    hashed_pw = hash_password(raw_password)

    try:
        await accountantDB.add_user(user_id, user_name, hashed_pw, region)

        # Сразу логиним пользователя
        await accountantDB.set_logged_in(user_id, user_name, 1)

        await state.set_state(MainMenu.logged_in)
        await message.answer(
            f"✅ Регистрация успешна!\nВы вошли как <b>{user_name}</b>.",
            reply_markup=get_main_menu_inline()
        )

    except Exception as e:
        await message.answer(f"❌ Ошибка при регистрации: {e}")
        await state.clear()