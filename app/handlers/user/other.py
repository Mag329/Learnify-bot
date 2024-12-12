from aiogram import F, Router, Bot
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery, InputMediaPhoto
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext

from datetime import datetime, timedelta

from config import ERROR_MESSAGE
import app.keyboards.user.keyboards as kb
from app.utils.database import AsyncSessionLocal, db, User, Settings
from app.utils.user.utils import get_marks
from app.states.user.states import MarkState


router = Router()


@router.message(F.text)
async def unknown_handler(message: Message):
    await message.answer("❌ <b>Неизвестная команда</b>\nВведите /start")
