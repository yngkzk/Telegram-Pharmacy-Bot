from aiogram.fsm.state import State, StatesGroup


class Register(StatesGroup):
    begin = State()
    login = State()
    region = State()
    password = State()
    confirm = State()


class LoginFSM(StatesGroup):
    choose_user = State()
    enter_password = State()


