from aiogram import F, Router, Bot
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery, InputMediaPhoto
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext

import asyncio
from datetime import datetime, timedelta

from config import ERROR_MESSAGE
import app.keyboards.user.keyboards as kb
from app.utils.database import AsyncSessionLocal, db, User, Settings
from app.utils.user.utils import get_schedule
from app.states.user.states import ScheduleState

router = Router()

# Словарь для хранения задач пользователей
user_tasks = {}

async def update_detailed_schedule(message: Message, user_id: int, date: datetime):
    detailed_schedule = await get_schedule(user_id, date, False)
    
    if message.html_text != detailed_schedule:
        await message.edit_text(detailed_schedule, reply_markup=kb.schedule)


async def cancel_previous_task(user_id: int):
    if user_id in user_tasks:
        task = user_tasks[user_id]
        if not task.done():
            task.cancel()


@router.message(F.text == "📅 Расписание")
async def schedule_handler(message: Message, state: FSMContext):
    await state.set_state(ScheduleState.date)
    await state.update_data(date=datetime.now())

    schedule_message = await message.answer(
        await get_schedule(message.from_user.id, datetime.now()),
        reply_markup=kb.schedule,
    )

    # Отменяем предыдущую задачу и создаём новую
    await cancel_previous_task(message.from_user.id)
    user_tasks[message.from_user.id] = asyncio.create_task(
        update_detailed_schedule(schedule_message, message.from_user.id, datetime.now())
    )


@router.callback_query(F.data == "schedule_left")
async def schedule_left_callback_handler(callback: CallbackQuery, state: FSMContext):
    await callback.answer()

    data = await state.get_data()

    date = data.get("date")

    if date:
        date = date - timedelta(days=1)
    else:
        date = datetime.now()

    await state.update_data(date=date)

    await callback.message.edit_text(
        await get_schedule(callback.from_user.id, date),
        reply_markup=kb.schedule,
    )

    # Отменяем предыдущую задачу и создаём новую
    await cancel_previous_task(callback.from_user.id)
    user_tasks[callback.from_user.id] = asyncio.create_task(
        update_detailed_schedule(callback.message, callback.from_user.id, date)
    )


@router.callback_query(F.data == "schedule_right")
async def schedule_right_callback_handler(callback: CallbackQuery, state: FSMContext):
    await callback.answer()

    data = await state.get_data()

    date = data.get("date")

    if date:
        date = date + timedelta(days=1)
    else:
        date = datetime.now()

    await state.update_data(date=date)

    await callback.message.edit_text(
        await get_schedule(callback.from_user.id, date),
        reply_markup=kb.schedule,
    )

    # Отменяем предыдущую задачу и создаём новую
    await cancel_previous_task(callback.from_user.id)
    user_tasks[callback.from_user.id] = asyncio.create_task(
        update_detailed_schedule(callback.message, callback.from_user.id, date)
    )


@router.callback_query(F.data == "schedule_today")
async def schedule_today_callback_handler(callback: CallbackQuery, state: FSMContext):
    await callback.answer()

    await state.set_state(ScheduleState.date)
    await state.update_data(date=datetime.now())

    await callback.message.edit_text(
        await get_schedule(callback.from_user.id, datetime.now()),
        reply_markup=kb.schedule,
    )

    # Отменяем предыдущую задачу и создаём новую
    await cancel_previous_task(callback.from_user.id)
    user_tasks[callback.from_user.id] = asyncio.create_task(
        update_detailed_schedule(callback.message, callback.from_user.id, datetime.now())
    )
