from aiogram.fsm.state import State, StatesGroup


class MainMenu(StatesGroup):
    main = State()  # 👤 Гость (Видит кнопку "Регистрация")
    logged_in = State()  # 🧑‍⚕️ Авторизован (Видит "Маршрут", "Аптека" и т.д.)