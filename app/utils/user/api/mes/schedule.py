# SPDX-FileCopyrightText: 2024-2026 Mag329
#
# SPDX-License-Identifier: MIT

import json
from datetime import datetime, timedelta, timezone

from aiogram.types import Message
from loguru import logger

from app.keyboards import user as kb
from app.utils.database import get_session, Settings, db
from app.utils.user.cache import get_ttl, redis_client
from app.utils.user.decorators import handle_api_error
from app.utils.user.utils import (
    EMOJI_NUMBERS,
    generate_deeplink,
    get_emoji_subject,
    get_student,
)

# Словарь для хранения задач пользователей
user_tasks = {}


@handle_api_error()
async def get_schedule(user_id, date_object, short=True, direction="right"):
    logger.info(f"Getting schedule for user {user_id}, date: {date_object.strftime('%Y-%m-%d')}, short={short}, direction={direction}")
    
    async with await get_session() as session:
        result = await session.execute(db.select(Settings).filter_by(user_id=user_id))
        settings: Settings = result.scalar_one_or_none()
        
        use_cache = False
        
        if settings and settings.experimental_features and settings.use_cache:
            short_cache_key = f"get_schedule:{user_id}:{date_object.strftime('%Y-%m-%d')}:{direction}:short"
            full_cache_key = f"get_schedule:{user_id}:{date_object.strftime('%Y-%m-%d')}:{direction}:full"

            if not short:
                cached_full = await redis_client.get(full_cache_key)
                if cached_full:
                    logger.debug(f"Cache hit for full schedule: user {user_id}, date {date_object.strftime('%Y-%m-%d')}")
                    data = json.loads(cached_full)
                    return data["text"], datetime.strptime(data["date"], "%Y-%m-%d")
                else:
                    logger.debug(f"Cache miss for full schedule: user {user_id}, date {date_object.strftime('%Y-%m-%d')}")

            use_cache = True
            logger.debug(f"Cache enabled for user {user_id}")
        else:
            logger.debug(f"Cache disabled for user {user_id}")

    try:
        api, user = await get_student(user_id)
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
    schedule = await api.get_events(
        person_id=user.person_id,
        mes_role=user.role,
        begin_date=date_object,
        end_date=date_object,
    )

    if (
        schedule.response
        and schedule.response[-1].finish_at < datetime.now(timezone.utc)
        and direction == "today"
        and short
        and settings.next_day_if_lessons_end_schedule
    ):
        old_date = date_object
        date_object += timedelta(days=1)
        logger.debug(f"Lessons ended for today, moving to next day: {date_object.strftime('%Y-%m-%d')} (was {old_date.strftime('%Y-%m-%d')})")
        
        schedule = await api.get_events(
            person_id=user.person_id,
            mes_role=user.role,
            begin_date=date_object,
            end_date=date_object,
        )

    # Пропуск пустых дней
    if settings.skip_empty_days_schedule and short:
        lessons_count = 0
        empty_days = 0
        
        logger.debug(f"Checking for empty days, starting from {date_object.strftime('%Y-%m-%d')}")

        while lessons_count <= 0 and empty_days <= 14:
            schedule = await api.get_events(
                person_id=user.person_id,
                mes_role=user.role,
                begin_date=date_object,
                end_date=date_object,
            )
            lessons_count = 0
            for event in schedule.response:
                if event.source != "PLAN":
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
            schedule = await api.get_events(
                person_id=user.person_id,
                mes_role=user.role,
                begin_date=original_date,
                end_date=original_date,
            )
            date_object = original_date

    text = f'📅 <b>Расписание на</b> {date_object.strftime("%d %B (%a)")}:\n\n'

    num = 0
    lessons_count = 0
    for event in schedule.response:
        if event.source != "PLAN":
            continue
        lessons_count += 1
        num += 1

        start_time = event.start_at.strftime("%H:%M")
        end_time = event.finish_at.strftime("%H:%M")

        subject_name = f'{EMOJI_NUMBERS.get(num, f"{num}️")} <a href="{await generate_deeplink(f'subject-menu-{event.subject_id}-{date_object.strftime("%d_%m_%Y")}')}">{await get_emoji_subject(event.subject_name)} <b>{event.subject_name}</b></a>'

        if not short:
            lesson_info = await api.get_lesson_schedule_item(
                profile_id=user.profile_id,
                lesson_id=event.id,
                student_id=user.student_id,
                type=event.source,
            )

            text += f'{subject_name} <i>({start_time}-{end_time})</i> {" <code>Н</code>" if event.is_missed_lesson else ""} {" 🟢" if event.start_at < datetime.now(timezone.utc) and datetime.now(timezone.utc) < event.finish_at else ""}\n    📍 {event.room_number}\n    👤 <i>{lesson_info.teacher.first_name[0]}. {lesson_info.teacher.middle_name[0]}. {lesson_info.teacher.last_name}</i> {" - 🔄 замена" if event.replaced else ""}\n\n'
        else:
            replaced_text = "\n    👤 - 🔄 замена"
            text += f'{subject_name} <i>({start_time}-{end_time})</i> {" <code>Н</code>" if event.is_missed_lesson else ""} {" 🟢" if event.start_at < datetime.now(timezone.utc) and datetime.now(timezone.utc) < event.finish_at else ""}\n    📍 {event.room_number}{replaced_text if event.replaced else ""}\n\n'

    if use_cache:
        cache_data = {"text": text, "date": date_object.strftime("%Y-%m-%d")}

        ttl = await get_ttl()

        if short and date_object == original_date:
            await redis_client.setex(short_cache_key, ttl, json.dumps(cache_data))
            logger.debug(f"Cached short schedule for user {user_id}, key: {short_cache_key}, TTL: {ttl}")
        else:
            await redis_client.setex(full_cache_key, ttl, json.dumps(cache_data))
            logger.debug(f"Cached full schedule for user {user_id}, key: {full_cache_key}, TTL: {ttl}")
    
    logger.info(f"Schedule retrieved for user {user_id}, {lessons_count} lessons on {date_object.strftime('%Y-%m-%d')}")
    return text, date_object


async def update_detailed_schedule(message: Message, user_id: int, date: datetime):
    logger.debug(f"Updating detailed schedule for user {user_id}, date: {date.strftime('%Y-%m-%d')}")
    
    try:
        detailed_schedule, _ = await get_schedule(user_id, date, False)
        if detailed_schedule:
            if message.html_text != detailed_schedule:
                await message.edit_text(detailed_schedule, reply_markup=kb.schedule)
                logger.debug(f"Detailed schedule updated for user {user_id}")
            else:
                logger.debug(f"Detailed schedule unchanged for user {user_id}")
    except Exception as e:
        logger.exception(f"Error updating detailed schedule for user {user_id}: {e}")


async def cancel_previous_task(user_id: int):
    if user_id in user_tasks:
        task = user_tasks[user_id]
        if not task.done():
            task.cancel()
            logger.debug(f"Cancelled previous task for user {user_id}")
        else:
            logger.debug(f"Previous task already completed for user {user_id}")
