from aiogram.types import ReplyKeyboardMarkup, KeyboardButton


# === Универсальный генератор клавиатуры ===
def build_keyboard(
    items: list[str],
    page: int = 0,
    row_width: int = 2,
    per_page: int = 4,
    add_back: bool = False
) -> ReplyKeyboardMarkup:

    keyboard = []

    start = page * per_page
    end = start + per_page
    page_items = items[start:end]

    for i in range(0, len(page_items), row_width):
        keyboard.append([
            KeyboardButton(text=name)
            for name in page_items[i:i + row_width]
        ])

    # — навигация —
    nav_row = []
    if page > 0:
        nav_row.append(KeyboardButton(text="⬅️ Назад"))
    if end < len(items):
        nav_row.append(KeyboardButton(text="➡️ Далее"))

    if nav_row:
        keyboard.append(nav_row)

    # — кнопка "Назад" —
    if add_back:
        keyboard.append([KeyboardButton(text="🔙 Меню")])

    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)


# === Главное меню ===
def get_main_kb() -> ReplyKeyboardMarkup:
    return build_keyboard(
        ["🧑‍⚕️ Пользователь", "🏥 Адм. панель", "💊 Отзывы", "📊 Отчёт"],
        row_width=2
    )


# === Меню Мед. представителей ===
def get_med_kb() -> ReplyKeyboardMarkup:
    return build_keyboard(
        ["🗺 Изменить маршрут", "🏥 ЛПУ", "🚪 Выйти из уч. записи"],
        row_width=2,
        add_back=True
    )


# === Меню Да / Нет ===
def get_yn_kb() -> ReplyKeyboardMarkup:
    return build_keyboard(["Да ✅", "Нет ❌"], row_width=2)


def get_cancel_kb() -> ReplyKeyboardMarkup:
    return build_keyboard(["Отменить 🚫"])


def get_region_kb() -> ReplyKeyboardMarkup:
    return build_keyboard(["АЛА", "ЮКО"], row_width=2)