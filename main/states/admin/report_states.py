from aiogram.fsm.state import StatesGroup, State

class AdminReportFSM(StatesGroup):
    choose_period = State()         # Выбор: Сегодня, Неделя, Месяц, Другое
    waiting_for_custom_date = State() # Если выбрали "Другое" (ввод текста)
    choose_employee = State()       # Выбор: Все или Конкретный