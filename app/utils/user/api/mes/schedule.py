# SPDX-FileCopyrightText: 2024-2026 Mag329
#
# SPDX-License-Identifier: MIT

import json
from datetime import datetime, timedelta, timezone

from octodiary.types.mobile.subjects import Subjects

from aiogram.types import Message
from loguru import logger
import pytz

from app.config.config import DEFAULT_LONG_CACHE_TTL
from app.keyboards import user as kb
from app.utils.database import get_session, Settings, db
from app.utils.user.cache import get_ttl, redis_client
from app.utils.user.decorators import handle_api_error
from app.utils.misc import morph
from app.utils.user.utils import (
    EMOJI_NUMBERS,
    generate_deeplink,
    get_emoji_subject,
    get_student,
    get_web_api,
)


@handle_api_error()
async def get_schedule(user_id, date_object, short=True, direction="right"):
    logger.info(f"Getting schedule for user {user_id}, date: {date_object.strftime('%Y-%m-%d')}, direction={direction}")
    
    cache_key = f"get_schedule:{user_id}:{date_object.strftime('%Y-%m-%d')}:{direction}"

    cached = await redis_client.get(cache_key)
    if cached:
        logger.debug(f"Cache hit for schedule: user {user_id}, date {date_object.strftime('%Y-%m-%d')}")
        data = json.loads(cached)
        return data["text"], datetime.strptime(data["date"], "%Y-%m-%d")
    else:
        logger.debug(f"Cache miss for schedule: user {user_id}, date {date_object.strftime('%Y-%m-%d')}")

    try:
        api, user = await get_student(user_id)
        web_api, _ = await get_web_api(user_id)
        if not api or not user:
            logger.error(f"Failed to get student data for user {user_id}")
            return "❌ <b>Ошибка</b>\n\nНе удалось получить данные ученика", date_object
    except Exception as e:
        logger.exception(f"Error getting student data for user {user_id}: {e}")
        return "❌ <b>Ошибка</b>\n\nНе удалось получить данные ученика", date_object

    original_date = date_object

    async with await get_session() as session:
        result = await session.execute(
            db.select(Settings).filter(Settings.user_id == user_id)
        )
        settings: Settings = result.scalar_one_or_none()

    logger.debug(f"Fetching schedule for {date_object.strftime('%Y-%m-%d')}")
    schedule = await web_api.get_schedule(
        student_id=user.student_id,
        date=date_object
    )

    if (
        schedule.activities
        and datetime.fromtimestamp(schedule.activities[-1].end_utc, tz=timezone.utc) < datetime.now(timezone.utc)
        and direction == "today"
        and settings.next_day_if_lessons_end_schedule
    ):
        old_date = date_object
        date_object += timedelta(days=1)
        logger.debug(f"Lessons ended for today, moving to next day: {date_object.strftime('%Y-%m-%d')} (was {old_date.strftime('%Y-%m-%d')})")
        
        schedule = await web_api.get_schedule(
            student_id=user.student_id,
            date=date_object
        )

    # Пропуск пустых дней
    if settings.skip_empty_days_schedule:
        lessons_count = 0
        empty_days = 0
        
        logger.debug(f"Checking for empty days, starting from {date_object.strftime('%Y-%m-%d')}")

        while lessons_count <= 0 and empty_days <= 14:
            schedule = await web_api.get_schedule(
                student_id=user.student_id,
                date=date_object
            )
            lessons_count = 0
            for activity in schedule.activities:
                if activity.type != "LESSON":
                    continue
                lessons_count += 1

            if lessons_count <= 0:
                empty_days += 1
                if direction in ["right", "today"]:
                    date_object += timedelta(days=1)  # Переход вправо
                else:
                    date_object -= timedelta(days=1)  # Переход влево
                logger.debug(f"No lessons on {date_object.strftime('%Y-%m-%d')}, moving to {date_object.strftime('%Y-%m-%d')}, empty days: {empty_days}")
            else:
                logger.debug(f"Found {lessons_count} lessons on {date_object.strftime('%Y-%m-%d')}")
                empty_days = 0

        if empty_days > 14:
            logger.warning(f"Too many empty days ({empty_days}) for user {user_id}, reverting to original date")
            schedule = await web_api.get_schedule(
                student_id=user.student_id,
                date=date_object
            )
            date_object = original_date

    text = f'📅 <b>Расписание на</b> {date_object.strftime("%d %B (%a)")}:\n\n'

    num = 0
    lessons_count = 0
    now = datetime.now(timezone.utc)
    
    for activity in schedule.activities:
        if activity.type == "LESSON":
            lessons_count += 1
            num += 1

            start_time = activity.begin_time
            end_time = activity.end_time
            
            
            subjects_list_cache_key = f"subjects_list:{user_id}"
            if await redis_client.exists(subjects_list_cache_key):
                cached_data = json.loads(await redis_client.get(subjects_list_cache_key))
                subjects_list = Subjects.model_validate(cached_data) 
            else:
                subjects_list = await api.get_subjects(
                    student_id=user.student_id, profile_id=user.profile_id
                )
                await redis_client.setex(subjects_list_cache_key, DEFAULT_LONG_CACHE_TTL, subjects_list.model_dump_json())
                
            subject_exists = next(
                (
                    True
                    for subject in subjects_list.payload
                    if subject.subject_id == activity.lesson.subject_id
                ),
                False,
            )
            
            if subject_exists:
                deeplink = f'<a href="{await generate_deeplink(f'subject-menu-{activity.lesson.subject_id}-{date_object.strftime("%d_%m_%Y")}')}">{await get_emoji_subject(activity.lesson.subject_name)} <b>{activity.lesson.subject_name}</b></a>'
            else:
                deeplink = f'<b>{await get_emoji_subject(activity.lesson.subject_name)}</b>'

            subject_name = f'{EMOJI_NUMBERS.get(num, f"{num}️")} {deeplink}'


            text += f'{subject_name} <i>({start_time}-{end_time})</i> {" <code>Н</code>" if activity.lesson.is_missed_lesson else ""} {" 🟢" if datetime.fromtimestamp(activity.begin_utc, tz=timezone.utc) < now and now < datetime.fromtimestamp(activity.end_utc, tz=timezone.utc) else ""}\n    📍 {activity.room_number}\n    👤 <i>{activity.lesson.teacher.first_name[0]}. {activity.lesson.teacher.middle_name[0]}. {activity.lesson.teacher.last_name}</i> {" - 🔄 замена" if activity.lesson.replaced else ""}\n\n'
        
        elif activity.type == "BREAK" and settings.show_active_break_in_schedule:
            break_start = datetime.fromtimestamp(activity.begin_utc, tz=timezone.utc)
            break_end = datetime.fromtimestamp(activity.end_utc, tz=timezone.utc)
            
            moscow_tz = pytz.timezone('Europe/Moscow')
            
            if break_start < now < break_end:
                break_start_time = break_start.astimezone(moscow_tz).strftime("%H:%M")
                break_end_time = break_end.astimezone(moscow_tz).strftime("%H:%M")
                
                activity_duration = activity.duration // 60
                minutes_morph = morph.parse('минута')[0]
                
                text += f'🟡 <b>Перемена</b> <i>({break_start_time}-{break_end_time})</i>\n    ⏱️ {activity_duration} {minutes_morph.make_agree_with_number(activity_duration).word}\n\n'

    cache_data = {"text": text, "date": date_object.strftime("%Y-%m-%d")}

    ttl = await get_ttl()

    cache_key = f"get_schedule:{user_id}:{date_object.strftime('%Y-%m-%d')}:{direction}"
    await redis_client.setex(cache_key, ttl, json.dumps(cache_data))
    logger.debug(f"Cached schedule for user {user_id}, key: {cache_key}, TTL: {ttl}")
    
    logger.info(f"Schedule retrieved for user {user_id}, {lessons_count} lessons on {date_object.strftime('%Y-%m-%d')}")
    return text, date_object
