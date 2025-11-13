from aiogram.fsm.state import State, StatesGroup


class MainMenu(StatesGroup):
    main = State()
    user = State()
    reports = State()
    admin = State()
    reviews = State()
    logged_in = State()
