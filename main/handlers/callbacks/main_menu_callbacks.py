from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext

# 🔥 НОВЫЕ ИМПОРТЫ РЕПОЗИТОРИЕВ
from infrastructure.database.repo.user_repo import UserRepository
from infrastructure.database.repo.pharmacy_repo import PharmacyRepository
from infrastructure.database.repo.report_repo import ReportRepository

# Импорты состояний
from states.add.prescription_state import PrescriptionFSM
from states.menu.main_menu_state import MainMenu

# Импорты клавиатур и утилит
from keyboard.inline import inline_buttons, menu_kb, admin_kb
from utils.logger.logger_config import logger
from utils.config.config import config

router = Router()


# ============================================================
# 🏠 ГЛАВНОЕ МЕНЮ (Обработка нажатий)
# ============================================================

@router.callback_query(F.data == "menu_route")
async def on_menu_route(
        callback: types.CallbackQuery,
        state: FSMContext,
        user_repo: UserRepository,
        pharmacy_repo: PharmacyRepository
):
    """Нажата кнопка 'Маршрут' (ЛПУ и Врачи)"""
    await state.set_state(PrescriptionFSM.choose_lpu)

    # 1. Достаем данные из текущей сессии логина
    data = await state.get_data()
    region = data.get("user_region")

    # Фолбэк (если вдруг бот перезагрузился и забыл сессию)
    if not region:
        user = await user_repo.get_user(callback.from_user.id)
        region = user.region if user and user.region else "АЛА"

    # 2. Достаем районы
    districts = await pharmacy_repo.get_districts_by_region(region)

    # 3. Формируем клавиатуру
    kb = await inline_buttons.get_district_inline(districts, state, prefix="district")
    await callback.message.edit_text("📍 Выберите район:", reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data == "menu_pharmacy")
async def on_menu_pharmacy(
        callback: types.CallbackQuery,
        state: FSMContext,
        user_repo: UserRepository,
        pharmacy_repo: PharmacyRepository
):
    """Нажата кнопка 'Аптека'"""
    await state.set_state(PrescriptionFSM.choose_apothecary)

    # Достаем регион из сессии
    data = await state.get_data()
    region = data.get("user_region")

    if not region:
        user = await user_repo.get_user(callback.from_user.id)
        region = user.region if user and user.region else "АЛА"

    districts = await pharmacy_repo.get_districts_by_region(region)

    keyboard = await inline_buttons.get_district_inline(districts, state, prefix="a_district")

    await callback.message.edit_text(
        f"🏥 <b>Раздел: Аптека</b>\nРегион: {region}\nВыберите район:",
        reply_markup=keyboard
    )
    await callback.answer()


@router.callback_query(F.data == "report_all")
async def on_report_menu(callback: types.CallbackQuery):
    """Нажата кнопка 'Отчёты'"""
    keyboard = inline_buttons.get_reports_inline()
    await callback.message.edit_text(
        "📊 <b>Отчёты</b>\nВыберите тип отчёта:",
        reply_markup=keyboard
    )
    await callback.answer()


@router.callback_query(F.data == "feedback_view")
async def on_feedback_menu(callback: types.CallbackQuery, reports_db: ReportRepository):
    """Нажата кнопка 'Отзывы'"""
    kb = await menu_kb.get_main_menu_inline(callback.from_user.id, reports_db)
    await callback.message.edit_text(
        "✍️ <b>Раздел отзывов</b>\nФункционал в разработке.",
        reply_markup=kb
    )
    await callback.answer()


@router.callback_query(F.data == "admin_panel")
async def on_admin_panel(callback: types.CallbackQuery):
    """Нажата кнопка 'Админка'"""
    if callback.from_user.id not in config.admin_ids:
        return await callback.answer("⛔️ У вас нет прав доступа к панели администратора!", show_alert=True)

    keyboard = admin_kb.get_admin_menu()
    await callback.message.edit_text(
        "⚙️ <b>Админ панель</b>\nВыберите действие:",
        reply_markup=keyboard
    )
    await callback.answer()


@router.callback_query(F.data == "user_log_out")
async def on_logout(callback: types.CallbackQuery, state: FSMContext, user_repo: UserRepository):
    """Выход из системы"""
    try:
        await user_repo.set_logged_in(callback.from_user.id, False)
    except Exception as e:
        logger.error(f"Logout error for user {callback.from_user.id}: {e}")

    await state.clear()
    await callback.message.edit_text(
        "🚪 Вы успешно вышли из системы.",
        reply_markup=menu_kb.get_guest_menu_inline()
    )
    await callback.answer()


# ============================================================
# 🔙 КНОПКА "НАЗАД" (Глобальная)
# ============================================================

@router.callback_query(F.data == "back_to_main")
async def back_to_main_menu(callback: types.CallbackQuery, state: FSMContext, reports_db: ReportRepository):
    """Возвращает пользователя в главное меню"""
    await state.clear()
    await state.set_state(MainMenu.logged_in)

    kb = await menu_kb.get_main_menu_inline(callback.from_user.id, reports_db)

    await callback.message.edit_text(
        "🔙 <b>Главное меню</b>\nВыберите раздел:",
        reply_markup=kb
    )
    await callback.answer()