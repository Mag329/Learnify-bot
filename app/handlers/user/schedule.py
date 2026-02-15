import asyncio
from datetime import datetime, timedelta

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from loguru import logger

from app.keyboards import user as kb
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
    user_id = message.from_user.id
    logger.info(f"User {user_id} requested schedule")
    
    await state.set_state(ScheduleState.date)

    text, new_date = await get_schedule(
        message.from_user.id, datetime.now(), direction="today"
    )

    await state.update_data(date=new_date)
    if text:
        logger.debug(f"Sending schedule for user {user_id}, date: {new_date.strftime('%Y-%m-%d')}")
        
        schedule_message = await message.answer(
            text,
            reply_markup=kb.schedule,
        )

        # Отменяем предыдущую задачу и создаём новую
        await cancel_previous_task(user_id)
        user_tasks[message.from_user.id] = asyncio.create_task(
            update_detailed_schedule(schedule_message, user_id, new_date)
        )
        logger.debug(f"Created background task for detailed schedule update for user {user_id}")
    else:
        logger.warning(f"No schedule data returned for user {user_id}")


@router.callback_query(F.data == "schedule_left")
async def schedule_left_callback_handler(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    await callback.answer()
    
    logger.info(f"User {user_id} navigated schedule left")

    data = await state.get_data()
    date = data.get("date", datetime.now())
    logger.debug(f"Current date from state: {date.strftime('%Y-%m-%d')}")

    new_date = date - timedelta(days=1)
    logger.debug(f"Moving to previous day: {new_date.strftime('%Y-%m-%d')}")

    text, new_date = await get_schedule(callback.from_user.id, new_date, direction="left")

    await state.update_data(date=new_date)
    if text:
        logger.debug(f"Updating schedule message for user {user_id}, new date: {new_date.strftime('%Y-%m-%d')}")
        await callback.message.edit_text(
            text,
            reply_markup=kb.schedule,
        )

        # Отменяем предыдущую задачу и создаём новую
        await cancel_previous_task(user_id)
        user_tasks[callback.from_user.id] = asyncio.create_task(
            update_detailed_schedule(callback.message, user_id, new_date)
        )
        logger.debug(f"Created background task for detailed schedule update for user {user_id}")
    else:
        logger.warning(f"No schedule data returned for user {user_id} on {new_date.strftime('%Y-%m-%d')}")


@router.callback_query(F.data == "schedule_right")
async def schedule_right_callback_handler(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    await callback.answer()
    
    logger.info(f"User {user_id} navigated schedule right")

    data = await state.get_data()
    date = data.get("date", datetime.now())
    logger.debug(f"Current date from state: {date.strftime('%Y-%m-%d')}")

    new_date = date + timedelta(days=1)
    logger.debug(f"Moving to next day: {new_date.strftime('%Y-%m-%d')}")

    text, new_date = await get_schedule(user_id, new_date, direction="right")

    await state.update_data(date=new_date)
    if text:
        logger.debug(f"Updating schedule message for user {user_id}, new date: {new_date.strftime('%Y-%m-%d')}")
        await callback.message.edit_text(
            text,
            reply_markup=kb.schedule,
        )

        # Отменяем предыдущую задачу и создаём новую
        await cancel_previous_task(user_id)
        user_tasks[callback.from_user.id] = asyncio.create_task(
            update_detailed_schedule(callback.message, user_id, new_date)
        )
        logger.debug(f"Created background task for detailed schedule update for user {user_id}")
    else:
        logger.warning(f"No schedule data returned for user {user_id} on {new_date.strftime('%Y-%m-%d')}")


@router.callback_query(F.data == "schedule_today")
async def schedule_today_callback_handler(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    await callback.answer()
    
    logger.info(f"User {user_id} navigated to today's schedule")

    await state.set_state(ScheduleState.date)

    text, new_date = await get_schedule(
        user_id, datetime.now(), direction="today"
    )

    await state.update_data(date=new_date)
    
    if text:
        logger.debug(f"Updating schedule message for user {user_id} to today: {new_date.strftime('%Y-%m-%d')}")
        await callback.message.edit_text(
            text,
            reply_markup=kb.schedule,
        )

        # Отменяем предыдущую задачу и создаём новую
        await cancel_previous_task(user_id)
        user_tasks[user_id] = asyncio.create_task(
            update_detailed_schedule(callback.message, user_id, new_date)
        )
        logger.debug(f"Created background task for detailed schedule update for user {user_id}")
    else:
        logger.warning(f"No schedule data returned for user {user_id} for today")