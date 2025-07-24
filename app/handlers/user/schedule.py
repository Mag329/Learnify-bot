import asyncio
from datetime import datetime, timedelta

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

import app.keyboards.user.keyboards as kb
from app.states.user.states import ScheduleState
from app.utils.user.api.mes.schedule import (
    cancel_previous_task,
    get_schedule,
    update_detailed_schedule,
    user_tasks,
)

router = Router()


@router.message(F.text == "📅 Расписание")
async def schedule_handler(message: Message, state: FSMContext):
    await state.set_state(ScheduleState.date)

    text, new_date = await get_schedule(
        message.from_user.id, datetime.now(), direction="today"
    )

    await state.update_data(date=new_date)
    if text:
        schedule_message = await message.answer(
            text,
            reply_markup=kb.schedule,
        )

        # Отменяем предыдущую задачу и создаём новую
        await cancel_previous_task(message.from_user.id)
        user_tasks[message.from_user.id] = asyncio.create_task(
            update_detailed_schedule(schedule_message, message.from_user.id, new_date)
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

    text, new_date = await get_schedule(callback.from_user.id, date, direction="left")

    await state.update_data(date=new_date)
    if text:
        await callback.message.edit_text(
            text,
            reply_markup=kb.schedule,
        )

        # Отменяем предыдущую задачу и создаём новую
        await cancel_previous_task(callback.from_user.id)
        user_tasks[callback.from_user.id] = asyncio.create_task(
            update_detailed_schedule(callback.message, callback.from_user.id, new_date)
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

    text, new_date = await get_schedule(callback.from_user.id, date, direction="right")

    await state.update_data(date=new_date)
    if text:
        await callback.message.edit_text(
            text,
            reply_markup=kb.schedule,
        )

        # Отменяем предыдущую задачу и создаём новую
        await cancel_previous_task(callback.from_user.id)
        user_tasks[callback.from_user.id] = asyncio.create_task(
            update_detailed_schedule(callback.message, callback.from_user.id, new_date)
        )


@router.callback_query(F.data == "schedule_today")
async def schedule_today_callback_handler(callback: CallbackQuery, state: FSMContext):
    await callback.answer()

    await state.set_state(ScheduleState.date)

    text, new_date = await get_schedule(
        callback.from_user.id, datetime.now(), direction="today"
    )

    await state.update_data(date=new_date)
    if text:
        await callback.message.edit_text(
            text,
            reply_markup=kb.schedule,
        )

        # Отменяем предыдущую задачу и создаём новую
        await cancel_previous_task(callback.from_user.id)
        user_tasks[callback.from_user.id] = asyncio.create_task(
            update_detailed_schedule(callback.message, callback.from_user.id, new_date)
        )
