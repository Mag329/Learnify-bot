from datetime import datetime, timedelta

from aiogram.fsm.context import FSMContext

import app.keyboards.user.keyboards as kb
from app.config import config
from app.config.config import BASE_QUARTER
from app.utils.user.decorators import handle_api_error
from app.utils.user.utils import (generate_deeplink, get_emoji_subject, get_mark_with_weight,
                                  get_student)


@handle_api_error()
async def get_marks(user_id, date_object):
    api, user = await get_student(user_id)
    marks = await api.get_marks(
        student_id=user.student_id,
        profile_id=user.profile_id,
        from_date=date_object,
        to_date=date_object,
    )

    text = f'🎓 <b>Оценки за</b> {date_object.strftime("%d %B (%a)")}:\n\n'

    for mark in marks.payload:
        mark_comment = (
            f"\n<blockquote>{mark.comment}</blockquote>" if mark.comment_exists else ""
        )
        
        subject_name = f'{await get_emoji_subject(mark.subject_name)} {mark.subject_name}'
        subject_name_with_link = f'<a href="{await generate_deeplink(f'subject-marks-{mark.subject_id}')}">{subject_name}</a>'
        
        text += f"<b>{subject_name_with_link}:</b>\n    <i><code>{await get_mark_with_weight(mark.value, mark.weight)} - {mark.control_form_name}</code></i>{mark_comment}\n\n"

    if len(marks.payload) == 0:
        text = f'❌ <b>У вас нет оценок </b>{date_object.strftime("%d %B (%a)")}'
    
    return text


async def get_marks_by_subject(user_id, subject_id):
    api, user = await get_student(user_id)
    
    marks_for_subject = await api.get_subject_marks_for_subject(
        student_id=user.student_id,
        profile_id=user.profile_id,
        subject_id=subject_id
    )
    
    text = f'🎓 <b>Оценки по {marks_for_subject.subject_name}</b>:\n\n'
    
    if not marks_for_subject.periods:
        text += "    ❌ <i>У вас нет оценок</i>"
    
    for period in marks_for_subject.periods:
        if not period.title.startswith(str(BASE_QUARTER)):
            continue
        
        text += (
            f'📊 <i>Средний балл:</i> {period.value}\n'
            f'🧮 <i>Всего оценок:</i> {len(period.marks)}\n'
        )
        
        for mark in period.marks:
            mark_text = await get_mark_with_weight(mark.value, mark.weight)
            date_str = f"📅 {mark.date.strftime('%d.%m.%Y')}" if mark.date else ""

            control_form_name = f"📘 {mark.control_form_name}\n" if mark.control_form_name else ""
            comment = f"💬 <code>{mark.comment}</code>\n" if mark.comment else ""

            # Компактный и аккуратный формат
            text += (
                f"\n<blockquote>{mark_text}</blockquote>\n"
                f"{date_str}\n"
                f'{control_form_name}'
                f'{comment}'
                f"───────────────\n"
            )

        text += "\n"
    
    return text


async def handle_marks_navigation(user_id: int, state: FSMContext, direction: str):
    data = await state.get_data()
    date = data.get("date", datetime.now())

    if direction == "left":
        date -= timedelta(days=1)
    elif direction == "right":
        date += timedelta(days=1)
    else:  # "today"
        date = datetime.now()

    await state.update_data(date=date)
    text = await get_marks(user_id, date)

    return text, kb.mark
