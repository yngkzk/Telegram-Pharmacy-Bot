from aiogram.fsm.state import StatesGroup, State


class PrescriptionFSM(StatesGroup):
    choose_lpu = State()
    choose_doctor = State()
    choose_meds = State()
    contract_terms = State()
    comments = State()
    confirm = State()

    choose_apothecary = State()
    choose_request = State()
    choose_remaining = State()
    comments_a = State()