from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext


class UpdateNotificationState(StatesGroup):
    text = State()
    confirm = State() 