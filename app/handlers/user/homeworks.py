from aiogram import F, Router, Bot
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery, InputMediaPhoto
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext

from datetime import datetime, timedelta

from config import ERROR_MESSAGE
import app.keyboards.user.keyboards as kb
from app.utils.database import AsyncSessionLocal, db, User, Settings
from app.utils.user.utils import get_homework, get_homework_by_subject
from app.states.user.states import HomeworkState

router = Router()


@router.message(F.text == "📚 Домашние задания")
async def howeworks_handler(message: Message, state: FSMContext):
    date = datetime.now()

    await state.set_state(HomeworkState.date)
    await state.update_data(date=date)
    text, new_date = await get_homework(message.from_user.id, date)

    if text:
        await message.answer(
            text,
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

    text, new_date = await get_homework(callback.from_user.id, date, 'left')
    
    await state.update_data(date=new_date)
    if text:
        await callback.message.edit_text(
            text,
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

    text, new_date = await get_homework(callback.from_user.id, date, 'right')
    
    await state.update_data(date=new_date)
    if text:
        await callback.message.edit_text(
            text,
            reply_markup=kb.homework,
        )


@router.callback_query(F.data == "homework_today")
async def homework_today_callback_handler(callback: CallbackQuery, state: FSMContext):
    await callback.answer()

    await state.set_state(HomeworkState.date)
    await state.update_data(date=datetime.now())

    text, new_date = await get_homework(callback.from_user.id, datetime.now())
    if text:
        await callback.message.edit_text(
            text,
            reply_markup=kb.homework,
        )


@router.callback_query(F.data == "choose_subject_homework")
async def choose_subject_homework_callback_handler(callback: CallbackQuery, state: FSMContext):
    await callback.answer()

    await callback.message.edit_text(
        "Выберите предмет",
        reply_markup=await kb.choice_subject(callback.from_user.id, 'homework'),
    )


@router.callback_query(F.data == "back_to_homework")
async def back_to_homework_callback_handler(callback: CallbackQuery, state: FSMContext):
    await callback.answer()

    data = await state.get_data()

    date = data.get("date")

    if not date:
        date = datetime.now()

    await state.update_data(date=date)

    await callback.message.edit_text(
        await get_homework(callback.from_user.id, date),
        reply_markup=kb.homework,
    )


@router.callback_query(F.data.startswith("select_subject_homework_"))
async def subject_homework_callback_handler(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()

    subject_id = int(callback.data.split("_")[-1])

    await state.update_data(subject_id=subject_id)
    await state.update_data(date=datetime.now())

    text = await get_homework_by_subject(callback.from_user.id, subject_id, datetime.now())
    await callback.answer()
    if text:
        await callback.message.edit_text(
            text,
            reply_markup=kb.subject_homework,
        )


@router.callback_query(F.data == "subject_homework_left")
async def homework_left_callback_handler(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()

    date = data.get("date")
    subject_id = data.get("subject_id")

    if not subject_id:
        await callback.message.edit_text("Выберите предмет", reply_markup=await kb.choice_subject(callback.from_user.id, 'homework'))
        return

    if date:
        date = date - timedelta(days=7)
    else:
        date = datetime.now()

    await state.update_data(date=date)

    text = await get_homework_by_subject(callback.from_user.id, subject_id, date)
    await callback.answer()
    if text:
        await callback.message.edit_text(
            text,
            reply_markup=kb.subject_homework,
        )


@router.callback_query(F.data == "subject_homework_right")
async def homework_right_callback_handler(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()

    date = data.get("date")
    subject_id = data.get("subject_id")

    if not subject_id:
        await callback.message.edit_text("Выберите предмет", reply_markup=await kb.choice_subject(callback.from_user.id, 'homework'))
        return

    if date:
        date = date + timedelta(days=7)
    else:
        date = datetime.now()

    await state.update_data(date=date)

    text = await get_homework_by_subject(callback.from_user.id, subject_id, date)
    await callback.answer()
    if text:
        await callback.message.edit_text(
            text,
            reply_markup=kb.subject_homework,
        )


@router.callback_query(F.data == "subject_homework_today")
async def homework_today_callback_handler(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()

    subject_id = data.get("subject_id")

    if not subject_id:
        await callback.message.edit_text("Выберите предмет", reply_markup=await kb.choice_subject(callback.from_user.id, 'homework'))
        return

    await state.set_state(HomeworkState.date)
    await state.update_data(date=datetime.now())

    text = await get_homework_by_subject(callback.from_user.id, subject_id, datetime.now())
    await callback.answer()
    if text:
        await callback.message.edit_text(
            text,
            reply_markup=kb.subject_homework,
        )
