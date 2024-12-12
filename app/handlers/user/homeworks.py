from aiogram import F, Router, Bot
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery, InputMediaPhoto
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext

from datetime import datetime, timedelta

from config import ERROR_MESSAGE
import app.keyboards.user.keyboards as kb
from app.utils.database import AsyncSessionLocal, db, User, Settings
from app.utils.user.utils import get_homework
from app.states.user.states import HomeworkState


router = Router()



@router.message(F.text == "📚 Домашние задания")
async def howeworks_handler(message: Message, state: FSMContext):
    date = datetime.now()
    
    await state.set_state(HomeworkState.date)
    await state.update_data(date=date)

    await message.answer(
        await get_homework(message.from_user.id, date),
        reply_markup=kb.homework,
    )
    
    
@router.callback_query(F.data == "homework_left")
async def homework_left_callback_handler(callback: CallbackQuery, state: FSMContext):
    await callback.answer()

    data = await state.get_data()

    date = data.get("date")

    if date:
        date = date - timedelta(days=1)
    else:
        date = datetime.now()

    await state.update_data(date=date)

    await callback.message.edit_text(
        await get_homework(callback.from_user.id, date),
        reply_markup=kb.homework,
    )


@router.callback_query(F.data == "homework_right")
async def homework_right_callback_handler(callback: CallbackQuery, state: FSMContext):
    await callback.answer()

    data = await state.get_data()

    date = data.get("date")

    if date:
        date = date + timedelta(days=1)
    else:
        date = datetime.now()

    await state.update_data(date=date)

    await callback.message.edit_text(
        await get_homework(callback.from_user.id, date),
        reply_markup=kb.homework,
    )


@router.callback_query(F.data == "homework_today")
async def homework_today_callback_handler(callback: CallbackQuery, state: FSMContext):
    await callback.answer()

    await state.set_state(HomeworkState.date)
    await state.update_data(date=datetime.now())

    await callback.message.edit_text(
        await get_homework(callback.from_user.id, datetime.now()),
        reply_markup=kb.homework,
    )
