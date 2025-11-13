from idlelib.editor import keynames

from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, KeyboardButtonPollType
from loader import accountantDB, pharmacyDB

from utils.logger.logger_config import logger


# === Универсальный генератор клавиатуры ===
def build_keyboard(
    items: list[str],
    page: int = 0,
    row_width: int = 2,
    per_page: int = 4,
    add_back: bool = False
) -> ReplyKeyboardMarkup:
    """
    Универсальный конструктор клавиатур с пагинацией.
    - Делит список кнопок на страницы
    - Добавляет навигацию ("⬅️ Назад" / "➡️ Далее") в одну строку
    - Может добавить кнопку возврата к предыдущему меню
    """
    keyboard = []

    # Определяем диапазон для текущей страницы
    start = page * per_page
    end = start + per_page
    page_items = items[start:end]

    # Разбиваем на строки по row_width
    for i in range(0, len(page_items), row_width):
        keyboard.append([KeyboardButton(text=name) for name in page_items[i:i + row_width]])

    # --- Добавляем навигационные кнопки ---
    nav_row = []
    if page > 0:  # если не первая страница
        nav_row.append(KeyboardButton(text="⬅️ Назад"))
    if end < len(items):  # если есть ещё страницы
        nav_row.append(KeyboardButton(text="➡️ Далее"))

    if nav_row:
        keyboard.append(nav_row)  # 👈 ОДНА строка для навигации

    # Добавляем кнопку "Назад" (в меню выше), если нужно
    if add_back and not any(btn.text == "🔙 Меню" for row in keyboard for btn in row):
        keyboard.append([KeyboardButton(text="🔙 Меню")])

    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

# === Главное меню ===
def get_main_kb() -> ReplyKeyboardMarkup:
    buttons = [
        "🧑‍⚕️ Пользователь",
        "🏥 Адм. панель",
        "💊 Отзывы",
        "📊 Отчёт"
    ]
    return build_keyboard(buttons, row_width=2)

# === Меню Мед. предов ===
def get_med_kb() -> ReplyKeyboardMarkup:
    buttons = [
        "🗺 Изменить маршрут",
        "🏥 ЛПУ",
        "🚪 Выйти из уч. записи"
    ]
    return build_keyboard(buttons, row_width=2, add_back=True)

# === Список пользователей из базы ===
def get_users_kb() -> ReplyKeyboardMarkup:
    user_list = accountantDB.get_user_list()
    return build_keyboard(user_list, row_width=2, add_back=True)

# === Клавиатура Да / Нет ===
def get_yn_kb() -> ReplyKeyboardMarkup:
    return build_keyboard(["Да ✅", "Нет ❌"], row_width=2)

def get_cancel_kb() -> ReplyKeyboardMarkup:
    return build_keyboard(["Отменить 🚫"])

# === Клавиатура с регионами ===
def get_region_kb() -> ReplyKeyboardMarkup:
    return build_keyboard(["АЛА", "ЮКО"], row_width=2)

# === Клавиатура по маршрутам ===
def get_district_kb() -> ReplyKeyboardMarkup:
    district_list = pharmacyDB.get_district_list()
    logger.info("Результат в buttons.py", district_list)
    return build_keyboard(district_list, per_page=4, add_back=True)