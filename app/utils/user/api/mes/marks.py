# SPDX-FileCopyrightText: 2024-2026 Mag329
#
# SPDX-License-Identifier: MIT

from datetime import datetime, timedelta
from loguru import logger

from aiogram.fsm.context import FSMContext

from app.keyboards import user as kb
from app.config.config import BASE_QUARTER
from app.utils.user.decorators import handle_api_error
from app.utils.user.utils import (
    generate_deeplink,
    get_emoji_subject,
    get_mark_with_weight,
    get_student,
)


@handle_api_error()
async def get_marks(user_id, date_object):
    logger.info(f"Getting marks for user {user_id}, date: {date_object.strftime('%Y-%m-%d')}")
    
    api, user = await get_student(user_id)
    if not api or not user:
        logger.error(f"Failed to get student data for user {user_id}")
        return f'❌ <b>Ошибка</b>\n\nНе удалось получить данные ученика'
    
    logger.debug(f"Fetching marks from API for user {user_id}")
    marks = await api.get_marks(
        student_id=user.student_id,
        profile_id=user.profile_id,
        from_date=date_object,
        to_date=date_object,
    )
    
    if not marks or not marks.payload:
        logger.info(f"No marks found for user {user_id} on {date_object.strftime('%Y-%m-%d')}")
        return f'❌ <b>У вас нет оценок </b>{date_object.strftime("%d %B (%a)")}'

    logger.debug(f"Found {len(marks.payload)} marks for user {user_id}")
    
    text = f'🎓 <b>Оценки за</b> {date_object.strftime("%d %B (%a)")}:\n\n'
    marks_count = 0

    for mark in marks.payload:
        marks_count += 1
        mark_comment = (
            f"\n<blockquote>{mark.comment}</blockquote>" if mark.comment_exists else ""
        )

        subject_name = (
            f"{await get_emoji_subject(mark.subject_name)} {mark.subject_name}"
        )
        subject_name_with_link = f'<a href="{await generate_deeplink(f'subject-marks-{mark.subject_id}')}">{subject_name}</a>'

        text += f"<b>{subject_name_with_link}:</b>\n    <i><code>{await get_mark_with_weight(mark.value, mark.weight)} - {mark.control_form_name}</code></i>{mark_comment}\n\n"

    if len(marks.payload) == 0:
        text = f'❌ <b>У вас нет оценок </b>{date_object.strftime("%d %B (%a)")}'

    logger.info(f"Successfully formatted {marks_count} marks for user {user_id}")
    return text


@handle_api_error()
async def get_marks_by_subject(user_id, subject_id):
    logger.info(f"Getting marks by subject for user {user_id}, subject_id: {subject_id}")
    
    api, user = await get_student(user_id)
    if not api or not user:
        logger.error(f"Failed to get student data for user {user_id}")
        return f'❌ <b>Ошибка</b>\n\nНе удалось получить данные ученика'

    logger.debug(f"Fetching marks for subject {subject_id} from API")
    marks_for_subject = await api.get_subject_marks_for_subject(
        student_id=user.student_id, profile_id=user.profile_id, subject_id=subject_id
    )

    if not marks_for_subject:
        logger.warning(f"No data returned for subject {subject_id}")
        return f'❌ <b>Ошибка</b>\n\nНе удалось получить оценки по предмету'
    
    text = f"🎓 <b>Оценки по {marks_for_subject.subject_name}</b>:\n\n"

    if not marks_for_subject.periods:
        logger.info(f"No periods found for subject {marks_for_subject.subject_name}")
        text += "    ❌ <i>У вас нет оценок</i>"
        return text
    
    periods_count = 0
    marks_count = 0

    for period in marks_for_subject.periods:
        if not period.title.startswith(str(BASE_QUARTER)):
            logger.debug(f"Skipping period {period.title} (not starting with {BASE_QUARTER})")
            continue
        
        periods_count += 1
        period_marks_count = len(period.marks)
        marks_count += period_marks_count
        
        logger.debug(f"Processing period {period.title}: {period_marks_count} marks, avg: {period.value}")
        
        text += (
            f"📊 <i>Средний балл:</i> {period.value}\n"
            f"🧮 <i>Всего оценок:</i> {len(period.marks)}\n"
        )

        for mark in period.marks:
            mark_text = await get_mark_with_weight(mark.value, mark.weight)
            date_str = f"📅 {mark.date.strftime('%d.%m.%Y')}" if mark.date else ""

            control_form_name = (
                f"📘 {mark.control_form_name}\n" if mark.control_form_name else ""
            )
            comment = f"💬 <code>{mark.comment}</code>\n" if mark.comment else ""

            text += (
                f"\n<blockquote>{mark_text}</blockquote>\n"
                f"{date_str}\n"
                f"{control_form_name}"
                f"{comment}"
                f"───────────────\n"
            )

        text += "\n"

    logger.info(f"Successfully formatted marks for subject {marks_for_subject.subject_name}: {periods_count} periods, {marks_count} total marks")
    return text


async def handle_marks_navigation(user_id: int, state: FSMContext, direction: str):
    logger.info(f"Handling marks navigation for user {user_id}, direction: {direction}")
    
    try:
        data = await state.get_data()
        date = data.get("date", datetime.now())
        logger.debug(f"Current date from state: {date.strftime('%Y-%m-%d')}")

        if direction == "left":
            date -= timedelta(days=1)
            logger.debug(f"Moving left: new date {date.strftime('%Y-%m-%d')}")
        elif direction == "right":
            date += timedelta(days=1)
            logger.debug(f"Moving right: new date {date.strftime('%Y-%m-%d')}")
        else:  # "today"
            date = datetime.now()
            logger.debug(f"Moving to today: {date.strftime('%Y-%m-%d')}")

        await state.update_data(date=date)
        text = await get_marks(user_id, date)

        logger.info(f"Marks navigation successful for user {user_id}, date: {date.strftime('%Y-%m-%d')}")
        
        return text, kb.mark
    
    except Exception as e:
        logger.exception(f"Error in marks navigation for user {user_id}: {e}")
        return "❌ <b>Ошибка</b>\n\nНе удалось загрузить оценки", kb.mark