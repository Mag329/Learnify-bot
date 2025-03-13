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


@router.message(F.text == "🎓 Оценки")
async def marks_handler(message: Message, state: FSMContext):
    date = datetime.now()

    await state.set_state(MarkState.date)
    await state.update_data(date=date)

    text = await get_marks(message.from_user.id, date)
    if text:
        await message.answer(text, reply_markup=kb.mark)


@router.callback_query(F.data == "mark_left")
async def mark_left_callback_handler(callback: CallbackQuery, state: FSMContext):
    await callback.answer()

    data = await state.get_data()

    date = data.get("date")

    if date:
        date = date - timedelta(days=1)
    else:
        date = datetime.now()

    await state.update_data(date=date)

    text = await get_marks(callback.from_user.id, date)
    if text:
        await callback.message.edit_text(
            text,
            reply_markup=kb.mark,
        )


@router.callback_query(F.data == "mark_right")
async def mark_right_callback_handler(callback: CallbackQuery, state: FSMContext):
    await callback.answer()

    data = await state.get_data()

    date = data.get("date")

    if date:
        date = date + timedelta(days=1)
    else:
        date = datetime.now()

    await state.update_data(date=date)

    text = await get_marks(callback.from_user.id, date)
    if text:
        await callback.message.edit_text(
            text,
            reply_markup=kb.mark,
        )


@router.callback_query(F.data == "mark_today")
async def mark_today_callback_handler(callback: CallbackQuery, state: FSMContext):
    await callback.answer()

    await state.set_state(MarkState.date)
    await state.update_data(date=datetime.now())

    text = await get_marks(callback.from_user.id, datetime.now())
    if text:
        await callback.message.edit_text(
            text,
            reply_markup=kb.mark,
        )



@router.callback_query(F.data == "choose_subject_marks")
async def choose_subject_homework_callback_handler(callback: CallbackQuery, state: FSMContext):
    await callback.answer()

    await callback.message.edit_text(
        "Выберите предмет",
        reply_markup=await kb.choice_subject(callback.from_user.id, 'marks'),
    )
    

@router.callback_query(F.data == "back_to_marks")
async def back_to_homework_callback_handler(callback: CallbackQuery, state: FSMContext):
    await callback.answer()

    data = await state.get_data()

    date = data.get("date")

    if not date:
        date = datetime.now()

    await state.update_data(date=date)

    await callback.message.edit_text(
        await get_marks(callback.from_user.id, date),
        reply_markup=kb.mark,
    )


@router.callback_query(F.data.startswith("select_subject_homework_"))
async def subject_homework_callback_handler(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()

    subject_id = int(callback.data.split("_")[-1])

    await state.update_data(subject_id=subject_id)
    await state.update_data(date=datetime.now())

    text = await get_marks_by_subject(callback.from_user.id, subject_id, datetime.now())
    await callback.answer()
    if text:
        await callback.message.edit_text(
            text,
            reply_markup=kb.subject_homework,
        )
