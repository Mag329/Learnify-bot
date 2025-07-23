from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup


class UpdateNotificationState(StatesGroup):
    text = State()
    confirm = State()
