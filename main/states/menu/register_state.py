from aiogram.fsm.state import State, StatesGroup

class Register(StatesGroup):
    region = State()   # Step 1: Input Region
    login = State()    # Step 2: Input Username
    password = State() # Step 3: Input Password
    confirm = State()  # Step 4: Repeat Password

class LoginFSM(StatesGroup):
    choose_user = State()    # Step 1: Select User from Inline Buttons
    enter_password = State() # Step 2: Type Password