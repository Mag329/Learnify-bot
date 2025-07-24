from datetime import datetime, timedelta

from aiogram.fsm.context import FSMContext

import app.keyboards.user.keyboards as kb
from app.utils.user.decorators import handle_api_error
from app.utils.user.utils import get_emoji_subject, get_mark_with_weight, get_student


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
        text += f"{await get_emoji_subject(mark.subject_name)} <b>{mark.subject_name}:</b>\n    <i><code>{await get_mark_with_weight(mark.value, mark.weight)} - {mark.control_form_name}</code></i>{mark_comment}\n\n"

    if len(marks.payload) == 0:
        text = f'❌ <b>У вас нет оценок </b>{date_object.strftime("%d %B (%a)")}'

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
