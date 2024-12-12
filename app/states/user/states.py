from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext


class AuthState(StatesGroup):
    main_message = State()
    login = State()
    password = State()
    sms_code_class = State()


class ScheduleState(StatesGroup):
    date = State()


class HomeworkState(StatesGroup):
    date = State()


class MarkState(StatesGroup):
    date = State()


class VisitState(StatesGroup):
    date = State()
