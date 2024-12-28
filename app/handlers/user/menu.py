from aiogram import F, Router, Bot
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery, InputMediaPhoto
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext

from datetime import datetime, timedelta

import app.keyboards.user.keyboards as kb
from app.utils.database import AsyncSessionLocal, db, User, Settings
from app.states.user.states import VisitState
from app.utils.user.utils import get_visits, get_profile, get_rating_rank_class

router = Router()


@router.message(F.text == "📋 Меню")
async def main_menu_handler(message: Message):
    await message.answer(
        "📋 Меню",
        reply_markup=kb.menu,
    )


@router.callback_query(F.data == "visits")
async def visits_handler(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(VisitState.date)
    await state.update_data(date=datetime.now())

    text = await get_visits(callback.from_user.id, datetime.now())
    if text:
        await callback.message.edit_text(
            text=text,
            reply_markup=kb.visits,
        )


@router.callback_query(F.data == "visits_left")
async def visits_left_handler(callback: CallbackQuery, state: FSMContext):
    await callback.answer()

    data = await state.get_data()

    date = data.get("date")

    if date:
        date = date - timedelta(weeks=1)
    else:
        date = datetime.now()

    await state.update_data(date=date)

    text = await get_visits(callback.from_user.id, date)
    if text:
        await callback.message.edit_text(
            text=text,
            reply_markup=kb.visits,
        )


@router.callback_query(F.data == "visits_right")
async def visits_left_handler(callback: CallbackQuery, state: FSMContext):
    await callback.answer()

    data = await state.get_data()

    date = data.get("date")

    if date:
        date = date + timedelta(weeks=1)
    else:
        date = datetime.now()

    await state.update_data(date=date)

    text = await get_visits(callback.from_user.id, date)
    if text:
        await callback.message.edit_text(
            text=text,
            reply_markup=kb.visits,
        )


@router.callback_query(F.data == "visits_this_week")
async def visits_today_callback_handler(callback: CallbackQuery, state: FSMContext):
    await callback.answer()

    await state.set_state(VisitState.date)
    await state.update_data(date=datetime.now())

    text = await get_visits(callback.from_user.id, datetime.now())
    if text:
        await callback.message.edit_text(
            text,
            reply_markup=kb.visits,
        )


@router.callback_query(F.data == "profile")
async def profile_callback_handler(callback: CallbackQuery):
    await callback.answer()

    text = await get_profile(callback.from_user.id)
    if text:
        await callback.message.edit_text(
            text=text,
            reply_markup=kb.back_to_menu,
        )


@router.callback_query(F.data == "back_to_menu")
async def back_to_menu_callback_handler(callback: CallbackQuery):
    await callback.answer()

    await callback.message.edit_text(
        text="📋 Меню",
        reply_markup=kb.menu,
    )


@router.callback_query(F.data == "rating_rank_class")
async def rating_rank_class_callback_handler(callback: CallbackQuery):
    await callback.answer()

    text = await get_rating_rank_class(callback.from_user.id)
    if text:
        await callback.message.edit_text(
            text=text,
            reply_markup=kb.back_to_menu,
        )