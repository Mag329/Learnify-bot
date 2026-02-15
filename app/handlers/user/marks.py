from datetime import datetime

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from loguru import logger

from app.keyboards import user as kb
from app.states.user.states import MarkState
from app.utils.user.api.mes.marks import (
    get_marks,
    get_marks_by_subject,
    handle_marks_navigation,
)

router = Router()


@router.message(F.text == "🎓 Оценки")
async def marks_handler(message: Message, state: FSMContext):
    user_id = message.from_user.id
    date = datetime.now()
    
    logger.info(f"User {user_id} requested marks")

    await state.set_state(MarkState.date)
    await state.update_data(date=date)

    text = await get_marks(user_id, date)
    await message.answer(text, reply_markup=kb.mark)
    logger.debug(f"Marks sent to user {user_id}")


@router.callback_query(F.data.in_({"mark_left", "mark_right", "mark_today"}))
async def marks_navigation_handler(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    await callback.answer()

    direction = callback.data.split("_")[-1]
    logger.info(f"User {user_id} navigating marks: {direction}")

    if direction == "today":
        await state.set_state(MarkState.date)

    text, markup = await handle_marks_navigation(
        user_id, state, direction
    )

    await callback.message.edit_text(text, reply_markup=markup)
    logger.debug(f"Marks navigation successful for user {user_id}")


@router.callback_query(F.data == "choose_subject_marks")
async def choose_subject_marks_callback_handler(
    callback: CallbackQuery, state: FSMContext
):
    user_id = callback.from_user.id
    await callback.answer()
    
    logger.debug(f"User {user_id} opening subject selection for marks")

    await callback.message.edit_text(
        "Выберите предмет",
        reply_markup=await kb.choice_subject(user_id, "marks"),
    )


@router.callback_query(F.data == "back_to_marks")
async def back_to_marks_callback_handler(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    date = datetime.now()

    await state.update_data(date=date)
    logger.debug(f"User {user_id} returning to marks")

    text = await get_marks(user_id, date)

    await callback.answer()
    await callback.message.edit_text(
        text,
        reply_markup=kb.mark,
    )
    logger.debug(f"Returned to marks for user {user_id}")


@router.callback_query(F.data.startswith("select_subject_marks_"))
async def subject_marks_callback_handler(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    data = callback.data.split("_")
    subject_id = int(data[3])
    new_message = True if data[-1] == "new" else False

    await state.update_data(subject_id=subject_id)
    logger.info(f"User {user_id} requested marks for subject_id={subject_id}")

    text = await get_marks_by_subject(user_id, subject_id)

    await callback.answer()

    if new_message:
        await callback.message.answer(
            text, reply_markup=kb.subject_marks_with_close
        )
        logger.debug(f"Subject marks sent as new message to user {user_id}")
    else:
        await callback.message.edit_text(text, reply_markup=kb.subject_marks)
        logger.debug(f"Subject marks updated in existing message for user {user_id}")
