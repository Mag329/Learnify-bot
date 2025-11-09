from datetime import datetime

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

import app.keyboards.user.keyboards as kb
from app.states.user.states import MarkState
from app.utils.user.api.mes.marks import (get_marks, get_marks_by_subject,
                                          handle_marks_navigation)

router = Router()


@router.message(F.text == "🎓 Оценки")
async def marks_handler(message: Message, state: FSMContext):
    date = datetime.now()

    await state.set_state(MarkState.date)
    await state.update_data(date=date)

    text = await get_marks(message.from_user.id, date)
    if text:
        await message.answer(text, reply_markup=kb.mark)
    else:
        await message.answer("📭 Сегодня оценок нет", reply_markup=kb.mark)


@router.callback_query(F.data.in_({"mark_left", "mark_right", "mark_today"}))
async def marks_navigation_handler(callback: CallbackQuery, state: FSMContext):
    await callback.answer()

    direction = callback.data.split("_")[-1]

    if direction == "today":
        await state.set_state(MarkState.date)

    text, markup = await handle_marks_navigation(
        callback.from_user.id, state, direction
    )

    if text:
        await callback.message.edit_text(text, reply_markup=markup)
    else:
        await callback.message.edit_text(
            "📭 Оценок за выбранную дату нет", reply_markup=markup
        )


@router.callback_query(F.data == "choose_subject_marks")
async def choose_subject_marks_callback_handler(
    callback: CallbackQuery, state: FSMContext
):
    await callback.answer()

    await callback.message.edit_text(
        "Выберите предмет",
        reply_markup=await kb.choice_subject(callback.from_user.id, "marks"),
    )
    

@router.callback_query(F.data == "back_to_marks")
async def back_to_marks_callback_handler(callback: CallbackQuery, state: FSMContext):
    date = datetime.now()

    await state.update_data(date=date)
    
    text = await get_marks(callback.from_user.id, date)

    await callback.answer()
    await callback.message.edit_text(
        text,
        reply_markup=kb.mark,
    )    

    
@router.callback_query(F.data.startswith("select_subject_marks_"))
async def subject_marks_callback_handler(callback: CallbackQuery, state: FSMContext):
    data = callback.data.split("_")
    subject_id = int(data[3])
    new_message = True if data[-1] == "new" else False

    await state.update_data(subject_id=subject_id)

    text = await get_marks_by_subject(
        callback.from_user.id, subject_id
    )

    await callback.answer()

    if text:
        if new_message:
            await callback.message.answer(text, reply_markup=kb.subject_marks_with_close)
        else:
            await callback.message.edit_text(text, reply_markup=kb.subject_marks)