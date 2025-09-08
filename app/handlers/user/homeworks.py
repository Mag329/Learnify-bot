from datetime import datetime

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

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
    date = datetime.now()

    await state.set_state(HomeworkState.date)

    text, new_date = await get_homework(message.from_user.id, date, direction="today")

    await state.update_data(date=new_date)
    if text:
        await message.answer(text, reply_markup=kb.homework)
    else:
        await message.answer(
            "❌ Домашних заданий на эту дату не найдено", reply_markup=kb.homework
        )


@router.callback_query(
    F.data.in_({"homework_left", "homework_right", "homework_today"})
)
async def general_homework_navigation(callback: CallbackQuery, state: FSMContext):
    direction = callback.data.split("_")[-1]
    text, date, markup = await handle_homework_navigation(
        callback.from_user.id, state, direction, subject_mode=False
    )
    
    await state.update_data(date=date)

    await callback.answer()

    if text:
        await callback.message.edit_text(text, reply_markup=markup)
    else:
        await callback.message.edit_text(
            "❌ Домашних заданий на эту дату не найдено", reply_markup=markup
        )


@router.callback_query(F.data == "choose_subject_homework")
async def choose_subject_homework_callback_handler(
    callback: CallbackQuery, state: FSMContext
):
    await callback.answer()

    await callback.message.edit_text(
        "Выберите предмет",
        reply_markup=await kb.choice_subject(callback.from_user.id, "homework"),
    )


@router.callback_query(F.data == "back_to_homework")
async def back_to_homework_callback_handler(callback: CallbackQuery, state: FSMContext):
    date = datetime.now()

    text, new_date = await get_homework(callback.from_user.id, date, direction="today")

    await state.update_data(date=new_date)

    await callback.answer()

    await callback.message.edit_text(
        text,
        reply_markup=kb.homework,
    )


@router.callback_query(F.data.startswith("select_subject_homework_"))
async def subject_homework_callback_handler(callback: CallbackQuery, state: FSMContext):
    subject_id = int(callback.data.split("_")[-1])

    await state.update_data(subject_id=subject_id)
    await state.update_data(date=datetime.now())

    text = await get_homework_by_subject(
        callback.from_user.id, subject_id, datetime.now()
    )

    await callback.answer()

    if text:
        await callback.message.edit_text(
            text,
            reply_markup=kb.subject_homework,
        )


@router.callback_query(
    F.data.in_(
        {"subject_homework_left", "subject_homework_right", "subject_homework_today"}
    )
)
async def subject_homework_navigation(callback: CallbackQuery, state: FSMContext):
    direction = callback.data.split("_")[-1]
    text, date, markup = await handle_homework_navigation(
        callback.from_user.id, state, direction, subject_mode=True
    )
    
    await state.update_data(date=date)

    await callback.answer()

    if text:
        await callback.message.edit_text(text, reply_markup=markup)
    elif markup:
        await callback.message.edit_text("Выберите предмет", reply_markup=markup)
