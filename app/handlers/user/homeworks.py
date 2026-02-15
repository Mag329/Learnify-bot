from datetime import datetime

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from loguru import logger

import app.keyboards.user.keyboards as kb
from app.states.user.states import HomeworkState
from app.utils.user.api.mes.homeworks import (
    get_homework,
    get_homework_by_subject,
    handle_homework_navigation,
)

router = Router()


@router.message(F.text == "📚 Домашние задания")
async def homeworks_handler(message: Message, state: FSMContext):
    user_id = message.from_user.id
    date = datetime.now()
    
    logger.info(f"User {user_id} requested homeworks")

    await state.set_state(HomeworkState.date)

    text, new_date = await get_homework(user_id, date, direction="today")

    await state.update_data(date=new_date)
    await message.answer(text, reply_markup=kb.homework)
    logger.debug(f"Homeworks sent to user {user_id}")


@router.callback_query(
    F.data.in_({"homework_left", "homework_right", "homework_today"})
)
async def general_homework_navigation(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    direction = callback.data.split("_")[-1]
    
    logger.info(f"User {user_id} navigating homeworks: {direction}")

    text, date, markup = await handle_homework_navigation(
        user_id, state, direction, subject_mode=False
    )

    await state.update_data(date=date)
    await callback.answer()
    await callback.message.edit_text(text, reply_markup=markup)
    
    logger.debug(f"Homework navigation successful for user {user_id}")


@router.callback_query(F.data == "choose_subject_homework")
async def choose_subject_homework_callback_handler(
    callback: CallbackQuery, state: FSMContext
):
    user_id = callback.from_user.id
    await callback.answer()
    
    logger.debug(f"User {user_id} opening subject selection for homeworks")

    await callback.message.edit_text(
        "Выберите предмет",
        reply_markup=await kb.choice_subject(user_id, "homework"),
    )


@router.callback_query(F.data == "back_to_homework")
async def back_to_homework_callback_handler(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    date = datetime.now()
    
    logger.debug(f"User {user_id} returning to homeworks")

    text, new_date = await get_homework(user_id, date, direction="today")

    await state.update_data(date=new_date)
    await callback.answer()
    await callback.message.edit_text(text, reply_markup=kb.homework)
    
    logger.debug(f"Returned to homeworks for user {user_id}")


@router.callback_query(F.data.startswith("select_subject_homework_"))
async def subject_homework_callback_handler(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    data = callback.data.split("_")
    subject_id = int(data[3])
    new_message = True if data[-1] == "new" else False
    if len(data) >= 5 and data[4] and data[4] != "new":
        try:
            date = datetime.strptime(data[4], "%d-%m-%Y")
            logger.debug(f"Parsed date from callback: {date.strftime('%Y-%m-%d')}")
        except ValueError:
            date = datetime.now()
            logger.warning(f"Failed to parse date from callback, using current date")
    else:
        date = datetime.now()

    await state.update_data(subject_id=subject_id)
    await state.update_data(date=date)
    
    logger.info(f"User {user_id} requested homeworks for subject_id={subject_id}")

    text = await get_homework_by_subject(callback.from_user.id, subject_id, date)

    await callback.answer()

    if text:
        if new_message:
            await callback.message.answer(
                text, reply_markup=kb.subject_homework_with_close
            )
            logger.debug(f"Subject homeworks sent as new message to user {user_id}")
        else:
            await callback.message.edit_text(text, reply_markup=kb.subject_homework)
            logger.debug(f"Subject homeworks updated in existing message for user {user_id}")


@router.callback_query(
    F.data.in_(
        {"subject_homework_left", "subject_homework_right", "subject_homework_today"}
    )
)
async def subject_homework_navigation(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    direction = callback.data.split("_")[-1]
    
    logger.info(f"User {user_id} navigating subject homeworks: {direction}")

    text, date, markup = await handle_homework_navigation(
        user_id, state, direction, subject_mode=True
    )

    await state.update_data(date=date)
    await callback.answer()
    await callback.message.edit_text(text, reply_markup=markup)
    
    logger.debug(f"Subject homework navigation successful for user {user_id}")