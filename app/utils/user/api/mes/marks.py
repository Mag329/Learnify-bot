# SPDX-FileCopyrightText: 2024-2026 Mag329
#
# SPDX-License-Identifier: MIT

from datetime import datetime, timedelta, timezone
import json
from loguru import logger

from aiogram.fsm.context import FSMContext

from app.keyboards import user as kb
from app.config.config import DEFAULT_LONG_CACHE_TTL
from app.utils.user.cache import redis_client
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
    
    cache_key = f"marks:{user_id}:{date_object.strftime('%Y-%m-%d')}"
    logger.debug(f"Cache key: {cache_key}")

    # Пытаемся получить данные из кэша
    cached_text = await redis_client.get(cache_key)
    if cached_text:
        logger.debug(
            f"Cache hit for marks: user {user_id}, date {date_object.strftime('%Y-%m-%d')}"
        )
        return cached_text
    
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
    
    await redis_client.setex(cache_key, 7200, text)
    logger.debug(f"Cached marks for user {user_id} with TTL 7200s")
    
    return text


@handle_api_error()
async def get_marks_by_subject(user_id, subject_id, need_period=False):
    logger.info(f"Getting marks by subject for user {user_id}, subject_id: {subject_id}")
    
    current_period_cache_key = f"current_period:{user_id}:{subject_id}"
    
    if not need_period:
        if await redis_client.exists(current_period_cache_key):
            current_period = int(await redis_client.get(current_period_cache_key))
            need_period = current_period
        
    cache_key = f"marks_subject:{user_id}:{subject_id}:{need_period}"
        
    if need_period:
        cached = await redis_client.get(cache_key)
        if cached:
            logger.debug(f"Cache key: {cache_key}")
            data = json.loads(cached)
            return data['text'], data['periods']
        
    
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

    subject_name_with_emoji = f'{await get_emoji_subject(marks_for_subject.subject_name)} {marks_for_subject.subject_name}'
    
    if not marks_for_subject.periods:
        logger.info(f"No periods found for subject {marks_for_subject.subject_name}")
        text = f"🎓 <b>Оценки по {subject_name_with_emoji}</b>\n    ❌ <i>У вас нет оценок</i>"
        return text
    
    period_num = 0
    marks_count = 0
    now = datetime.now()
    
    
    for period in marks_for_subject.periods:
        period_num += 1
        
        if period.start < now < period.end:            
            current_period = period_num
            await redis_client.setex(current_period_cache_key, DEFAULT_LONG_CACHE_TTL, str(current_period))

            if not need_period:
                need_period = current_period
        
        
        if need_period == period_num:
            text = f"🎓 <b>Оценки по {subject_name_with_emoji}</b> ({period.title}):\n\n"
        
            period_marks_count = len(period.marks)
            marks_count += period_marks_count
            
            logger.debug(f"Processing period {period.title}: {period_marks_count} marks, avg: {period.value}")
            
            marks = []
            for mark in period.marks:
                if mark.value.isdigit():
                    mark_value = int(mark.value)
                    weight = int(mark.weight)
                    marks.extend([mark_value] * weight)
            
            text += (
                f"📊 <i>Средний балл:</i> {period.value}\n"
                f"🧮 <i>Всего оценок:</i> {len(marks)}\n"
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
            
    periods = [
        {
            'num': num, 
            'title': period.title, 
            'current': True if current_period == num else False
        } 
        for num, period in enumerate(marks_for_subject.periods, start=1)
    ]

    logger.info(f"Successfully formatted marks for subject {marks_for_subject.subject_name}: period {period_num}, {marks_count} total marks")
    
    cache_data = {
        'text': text,
        'periods': periods
    }
    
    await redis_client.setex(cache_key, 7200, json.dumps(cache_data, ensure_ascii=False))
    logger.debug(f"Cached marks by subject for user {user_id} with TTL 7200s")
    
    return text, periods


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