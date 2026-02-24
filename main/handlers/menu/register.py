from aiogram import Router, types, F, Bot
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder

# 🔥 НОВЫЕ ЧИСТЫЕ ИМПОРТЫ РЕПОЗИТОРИЕВ
from infrastructure.database.repo.user_repo import UserRepository
from infrastructure.database.repo.report_repo import ReportRepository

from utils.config.config import config
from utils.text.pw import hash_password, check_password as verify_password

from states.menu.register_state import Register, LoginFSM
from states.menu.main_menu_state import MainMenu
from keyboard.inline.menu_kb import get_main_menu_inline, get_guest_menu_inline

router = Router()


# ============================================================
# 🚪 ВЫБОР ДЕЙСТВИЯ (АВТОРИЗАЦИЯ)
# ============================================================
@router.callback_query(F.data == "start_registration")
async def show_auth_choice(callback: types.CallbackQuery, state: FSMContext):
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
    await callback.message.edit_text("🏠 Вы вернулись в меню гостя.", reply_markup=get_guest_menu_inline())
    await callback.answer()


# ============================================================
# 👤 ЛОГИН (СУЩЕСТВУЮЩИЙ ПОЛЬЗОВАТЕЛЬ)
# ============================================================
@router.callback_query(F.data == "auth_existing")
async def start_login_flow(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(LoginFSM.choose_user)
    await callback.message.edit_text("✍️ <b>Введите ваш логин</b> (Имя пользователя):")
    await callback.answer()


@router.message(LoginFSM.choose_user)
async def process_login_input(
        message: types.Message,
        state: FSMContext,
        user_repo: UserRepository  # <-- Работает магия Middleware!
):
    username_input = message.text.strip()
    user = await user_repo.get_user_by_username(username_input)

    if not user:
        return await message.answer("❌ Пользователь с таким логином не найден. Проверьте опечатку:")

    if not user.is_approved:
        return await message.answer("⏳ Ваш аккаунт еще на проверке у администратора. Ожидайте.")

    await state.update_data(username=username_input)
    await state.set_state(LoginFSM.enter_password)

    await message.answer(
        f"🔑 Профиль найден: <b>{username_input}</b>\n\n✍️ Введите ваш пароль:"
    )


@router.message(LoginFSM.enter_password)
async def check_password_handler(
        message: types.Message,
        state: FSMContext,
        user_repo: UserRepository,
        reports_db: ReportRepository
):
    password_input = message.text
    try:
        await message.delete()
    except Exception:
        pass

    data = await state.get_data()
    username = data.get("username")
    user_id = message.from_user.id

    user = await user_repo.get_user_by_username(username)

    if not user:
        return await message.answer("❌ Ошибка: Пользователь не найден.")

    if verify_password(password_input, user.user_password):
        await user_repo.set_logged_in(user_id, True)

        # 🔥 МАГИЧЕСКАЯ СТРОЧКА: Сохраняем регион именно этого аккаунта в сессию!
        await state.update_data(user_region=user.region)

        kb = await get_main_menu_inline(user_id, reports_db)
        await state.set_state(MainMenu.logged_in)
        await message.answer(f"✅ Успешный вход!\nДобро пожаловать, <b>{username}</b>!", reply_markup=kb)
    else:
        await message.answer("❌ Неверный пароль. Попробуйте снова:")


# ============================================================
# 🆕 РЕГИСТРАЦИЯ (НОВЫЙ ПОЛЬЗОВАТЕЛЬ)
# ============================================================
@router.callback_query(F.data == "auth_new")
async def start_register_flow(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(Register.region)
    await callback.message.edit_text("📝 <b>Регистрация</b>\n\nВведите ваш <b>Регион</b> (например: АЛА или ЮКО):")
    await callback.answer()


@router.message(Register.region)
async def get_region(message: types.Message, state: FSMContext):
    await state.update_data(region=message.text)
    await state.set_state(Register.login)
    await message.answer("👤 Придумайте <b>Логин</b> (Имя пользователя):")


@router.message(Register.login)
async def get_login(message: types.Message, state: FSMContext, user_repo: UserRepository):
    username_input = message.text.strip()

    # Сразу проверяем, занят ли логин (улучшаем UX)
    existing_user = await user_repo.get_user_by_username(username_input)
    if existing_user:
        return await message.answer("❌ Этот логин уже занят. Придумайте другой:")

    await state.update_data(login=username_input)
    await state.set_state(Register.password)
    await message.answer("🔑 Придумайте <b>Пароль</b>:")


@router.message(Register.password)
async def get_password(message: types.Message, state: FSMContext):
    await state.update_data(password=message.text)
    try:
        await message.delete()
    except Exception:
        pass
    await state.set_state(Register.confirm)
    await message.answer("🔐 <b>Повторите пароль</b> для подтверждения:")


@router.message(Register.confirm)
async def confirm_password(
        message: types.Message,
        state: FSMContext,
        bot: Bot,
        user_repo: UserRepository
):
    data = await state.get_data()
    try:
        await message.delete()
    except Exception:
        pass

    if message.text != data["password"]:
        await state.set_state(Register.password)
        return await message.answer("❌ Пароли не совпадают! Придумайте пароль заново:")

    user_id = message.from_user.id
    user_name = data["login"]
    raw_password = data["password"]
    region = data["region"]

    hashed_pw = hash_password(raw_password)

    try:
        await user_repo.create_user(user_id, user_name, hashed_pw, region)
        await message.answer("✅ <b>Заявка отправлена!</b>\n\nВаш аккаунт находится на проверке у администратора.")

        # Уведомление админам
        admin_text = (
            f"🔔 <b>Новая регистрация!</b>\n"
            f"👤 Имя: {user_name}\n"
            f"📍 Регион: {region}\n"
            f"🆔 Telegram ID: {user_id}\n\n"
            f"Используйте панель администратора для подтверждения."
        )
        for admin_id in config.admin_ids:
            try:
                await bot.send_message(admin_id, admin_text)
            except Exception:
                pass

        await state.clear()
    except Exception as e:
        await message.answer("❌ Ошибка регистрации. Попробуйте позже.")
        print(f"Registration Error: {e}")