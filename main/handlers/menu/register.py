from aiogram import Router, types, F, Bot
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from db.reports import ReportRepository

# Импортируем класс базы для подсказок типов (Type Hinting)
from db.database import BotDB
# Импортируем конфиг для доступа к ID админов
from utils.config.settings import config
# Хеширование паролей
from utils.text.pw import hash_password

# Состояния
from states.menu.register_state import Register, LoginFSM
from states.menu.main_menu_state import MainMenu

# Клавиатуры
from keyboard.inline.menu_kb import get_main_menu_inline, get_guest_menu_inline

router = Router()


# ============================================================
# 🚪 ВХОД В СИСТЕМУ
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
    # Здесь можно добавить логику возврата к главному меню
    await callback.message.edit_text(
        "🏠 Вы вернулись в меню гостя.",
        reply_markup=get_guest_menu_inline()
    )
    await callback.answer()


# ============================================================
# 👤 ЛОГИН (СУЩЕСТВУЮЩИЙ ПОЛЬЗОВАТЕЛЬ)
# ============================================================

@router.callback_query(F.data == "auth_existing")
async def start_login_flow(callback: types.CallbackQuery, state: FSMContext, accountant_db: BotDB):
    """
    Магия DI: accountant_db прилетает сюда автоматически из main.py
    """
    users = await accountant_db.get_user_list()

    if not users:
        await callback.message.edit_text(
            "⚠️ В базе пока нет подтвержденных пользователей.",
            reply_markup=get_guest_menu_inline()
        )
        return

    builder = InlineKeyboardBuilder()
    for user in users:
        # Важно: если user содержит пробелы или спецсимволы, это может сломать callback.
        # Лучше использовать ID, но пока оставим как есть.
        builder.button(text=f"👤 {user}", callback_data=f"login_user_{user}")

    builder.button(text="🔙 Назад", callback_data="start_registration")
    builder.adjust(2)

    await state.set_state(LoginFSM.choose_user)
    await callback.message.edit_text(
        "👇 <b>Выберите свой профиль:</b>",
        reply_markup=builder.as_markup()
    )
    await callback.answer()


@router.callback_query(F.data.startswith("login_user_"), LoginFSM.choose_user)
async def user_selected(callback: types.CallbackQuery, state: FSMContext):
    username = callback.data.split("login_user_")[1]

    await state.update_data(username=username)
    await state.set_state(LoginFSM.enter_password)

    await callback.message.edit_text(
        f"🔑 Профиль: <b>{username}</b>\n\n"
        "✍️ Введите ваш пароль:",
        reply_markup=None
    )
    await callback.answer()


@router.message(LoginFSM.enter_password)
async def check_password(
    message: types.Message,
    state: FSMContext,
    accountant_db: BotDB,
    reports_db: ReportRepository
):
    password = message.text
    data = await state.get_data()
    username = data.get("username")
    user_id = message.from_user.id

    if await accountant_db.check_password(username, password):
        await accountant_db.set_logged_in(user_id, username, 1)

        # ВОТ ЗДЕСЬ ИЗМЕНЕНИЕ: передаем reports_db в функцию меню
        kb = await get_main_menu_inline(user_id, reports_db)

        await state.set_state(MainMenu.logged_in)
        await message.answer(
            f"✅ Добро пожаловать, <b>{username}</b>!",
            reply_markup=kb
        )
    else:
        await message.answer("❌ Неверный пароль. Попробуйте снова:")


# ============================================================
# 🆕 РЕГИСТРАЦИЯ (НОВЫЙ ПОЛЬЗОВАТЕЛЬ)
# ============================================================

@router.callback_query(F.data == "auth_new")
async def start_register_flow(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(Register.region)
    await callback.message.edit_text(
        "📝 <b>Регистрация</b>\n\n"
        "Введите ваш <b>Регион</b> (например: АЛА или ЮКО):"
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
    # Тут можно добавить проверку на уникальность логина через accountant_db
    await state.update_data(login=username)
    await state.set_state(Register.password)
    await message.answer("🔑 Придумайте <b>Пароль</b>:")


@router.message(Register.password)
async def get_password(message: types.Message, state: FSMContext):
    await state.update_data(password=message.text)
    try:
        await message.delete()
    except:
        pass
    await state.set_state(Register.confirm)
    await message.answer("🔐 <b>Повторите пароль</b> для подтверждения:")


@router.message(Register.confirm)
async def confirm_password(message: types.Message, state: FSMContext, accountant_db: BotDB, bot: Bot):
    """
    Сюда прилетает и база (accountant_db), и сам бот (bot), чтобы слать уведомления админам.
    """
    data = await state.get_data()

    try:
        await message.delete()
    except:
        pass

    if message.text != data["password"]:
        await message.answer("❌ Пароли не совпадают! Придумайте пароль заново:")
        await state.set_state(Register.password)
        return

    # --- Сбор данных ---
    user_id = message.from_user.id
    user_name = data["login"]
    raw_password = data["password"]
    region = data["region"]

    # Хешируем пароль ПЕРЕД сохранением
    hashed_pw = hash_password(raw_password)

    try:
        # Сохраняем в БД (теперь user_password хранит хеш)
        await accountant_db.add_user(user_id, user_name, hashed_pw, region)

        # Уведомление пользователю
        await message.answer(
            "✅ <b>Заявка отправлена!</b>\n\n"
            "Ваш аккаунт находится на проверке у администратора.\n"
            "Как только вам дадут доступ, бот пришлет уведомление."
        )

        # 🔔 Уведомление АДМИНАМ (Теперь это работает!)
        admin_text = (
            f"🔔 <b>Новая регистрация!</b>\n"
            f"👤 Имя: {user_name}\n"
            f"📍 Регион: {region}\n"
            f"🆔 Telegram ID: {user_id}\n\n"
            f"Используйте /admin чтобы подтвердить."
        )

        for admin_id in config.admin_ids:
            try:
                await bot.send_message(admin_id, admin_text)
            except Exception as e:
                # Если админ заблокировал бота, не роняем код
                print(f"Failed to send admin notification to {admin_id}: {e}")

        await state.clear()

    except Exception as e:
        await message.answer(f"❌ Ошибка при регистрации: {e}")
        # Логируем ошибку, чтобы видеть в консоли
        print(f"Registration Error: {e}")
        await state.clear()