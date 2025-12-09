from aiogram.fsm.state import State, StatesGroup


# === FSM состояния ===
class AddDoctor(StatesGroup):
    waiting_for_name = State()
    waiting_for_spec = State()
    waiting_for_number = State()
    waiting_for_bd = State()
    waiting_for_confirmation = State()

class AddPharmacy(StatesGroup):
    waiting_for_name = State()
    waiting_for_url = State()
    waiting_for_confirmation = State()


class AddApothecary(StatesGroup):
    waiting_for_name = State()
    waiting_for_url = State()