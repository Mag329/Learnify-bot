# SPDX-FileCopyrightText: 2024-2026 Mag329
#
# SPDX-License-Identifier: MIT

import json
from datetime import datetime, timedelta, timezone
from loguru import logger

from aiogram.fsm.context import FSMContext

from app.keyboards import user as kb
from app.config.config import DEFAULT_SHORT_CACHE_TTL, LEARNIFY_API_TOKEN
from app.utils.database import get_session, Homework, Settings, db
from app.utils.misc import has_numbers
from app.utils.user.cache import get_ttl, redis_client
from app.utils.user.decorators import handle_api_error
from app.utils.user.utils import generate_deeplink, get_emoji_subject, get_student

# Temp dicts
temp_events = {}


@handle_api_error()
async def get_homework(user_id, date_object, direction="right"):
    logger.info(f"Getting homework for user {user_id}, date: {date_object.strftime('%Y-%m-%d')}, direction: {direction}")

    cache_key = f"homeworks:{user_id}:{date_object.strftime('%Y-%m-%d')}:{direction if direction != 'to_date' else 'today'}"
    logger.debug(f"Cache key: {cache_key}")
    
    # Чтение кэша только если это не "to_date"
    if direction != "to_date":
        cached_full = await redis_client.get(cache_key)
        if cached_full:
            logger.debug(f"Cache hit for homework: user {user_id}, date {date_object.strftime('%Y-%m-%d')}")
            
            data = json.loads(cached_full)
            return data["text"], datetime.strptime(data["date"], "%Y-%m-%d")
        else:
            logger.debug(f"Cache miss for homework: user {user_id}, date {date_object.strftime('%Y-%m-%d')}")

    api, user = await get_student(user_id)
    if not api or not user:
        logger.error(f"Failed to get student data for user {user_id}")
        return f'❌ <b>Ошибка</b>\n\nНе удалось получить данные ученика', date_object

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

    # Проверка на окончание уроков
    if (
        schedule.response
        and schedule.response[-1].finish_at < datetime.now(timezone.utc)
        and direction == "today"
        and settings
        and settings.next_day_if_lessons_end_homeworks
    ):
        old_date = date_object
        date_object += timedelta(days=1)
        logger.debug(f"Lessons ended for today, moving to next day: {date_object.strftime('%Y-%m-%d')} (was {old_date.strftime('%Y-%m-%d')})")
        
        homework = await api.get_homeworks(
            student_id=user.student_id,
            profile_id=user.profile_id,
            from_date=date_object,
            to_date=date_object,
        )

    # Пропуск пустых дней
    if settings.skip_empty_days_homeworks and direction != "to_date":
        homework_count = 0
        empty_days = 0
        original_for_empty = date_object
        
        logger.debug(f"Checking for empty homework days, starting from {date_object.strftime('%Y-%m-%d')}")

        while homework_count <= 0 and empty_days <= 14:
            homework = await api.get_homeworks(
                student_id=user.student_id,
                profile_id=user.profile_id,
                from_date=date_object,
                to_date=date_object,
            )
            homework_count = len(homework.payload)

            if homework_count <= 0:
                empty_days += 1
                if direction in ["right", "today"]:
                    date_object += timedelta(days=1)  # Переход вправо
                else:
                    date_object -= timedelta(days=1)  # Переход влево
                logger.debug(f"No homework on {original_for_empty.strftime('%Y-%m-%d')}, moving to {date_object.strftime('%Y-%m-%d')}, empty days: {empty_days}")
            else:
                logger.debug(f"Found {homework_count} homeworks on {date_object.strftime('%Y-%m-%d')}")
                empty_days = 0

        if empty_days > 14:
            logger.warning(f"Too many empty days ({empty_days}) for user {user_id}, reverting to original date")
            homework = await api.get_homeworks(
                student_id=user.student_id,
                profile_id=user.profile_id,
                from_date=original_date,
                to_date=original_date,
            )
            date_object = original_date

    else:
        logger.debug(f"Fetching homework for {date_object.strftime('%Y-%m-%d')}")
        homework = await api.get_homeworks(
            student_id=user.student_id,
            profile_id=user.profile_id,
            from_date=date_object,
            to_date=date_object,
        )
        
    if not homework:
        logger.error(f"No homework data returned for user {user_id}")
        return f'❌ <b>Ошибка</b>\n\nНе удалось получить домашние задания', date_object

    text = f'📚 <b>Домашние задания на</b> {date_object.strftime("%d %B (%a)")}:\n\n'
    sorted_homeworks = sorted(homework.payload, key=lambda x: x.subject_name)

    homework_count = len(homework.payload)
    logger.debug(f"Found {homework_count} homeworks")
    
    for task in sorted_homeworks:
        description = task.description.rstrip("\n")
        materials_amount = sum(
            1 for m in task.materials if m.type not in ["attachments"]
        )
        materials = (
            f"<i> (Для выполнения: {materials_amount})</i>" if materials_amount else ""
        )
        description_code = (
            f"<code>{description}</code>"
            if "https://" not in description
            else f"<i>{description}</i>"
        )
        is_done = task.is_done

        async with await get_session() as session:
            result = await session.execute(
                db.select(Homework).filter_by(
                    task=description, subject_id=task.subject_id
                )
            )
            homework_db = result.scalar_one_or_none()
            if not homework_db:
                homework_db = Homework(task=description, subject_id=task.subject_id)
                session.add(homework_db)
                await session.commit()
                await session.refresh(homework_db)
                logger.debug(f"Created new Homework record for task: {description[:50]}...")

        # Генерация ссылок
        if settings.enable_homework_done_function:
            link = f'<a href="{await generate_deeplink(f'done-homework-{task.homework_entry_student_id}-{"True" if not is_done else "False"}')}">'
            link += "◼️</a>" if not is_done else "✔️</a>"
            description_text = f"<s>{description}</s>" if is_done else description_code
        else:
            link = ""
            description_text = description_code
        
        if LEARNIFY_API_TOKEN:
            gdz_link = (
                f'<a href="{await generate_deeplink(f'autogdz-{homework_db.id}')}">⚡</a>'
                if await has_numbers(description)
                else ""
            )

            description_text = f"{description_text} {gdz_link}"

        subject_name = f"{await get_emoji_subject(task.subject_name)} <b>{task.subject_name}</b>{materials}"
        subject_name_with_link = f'<a href="{await generate_deeplink(f'subject-homework-{task.subject_id}-{task.date_prepared_for.strftime("%d_%m_%Y")}')}">{subject_name}</a>'

        text += f"{subject_name_with_link}<b>:</b>\n    {link} {description_text}\n\n"

    if len(homework.payload) == 0:
        text = f'❌ <b>У вас нет домашних заданий на </b>{date_object.strftime("%d %B (%a)")}'
        logger.debug(f"No homeworks found for user {user_id} on {date_object.strftime('%Y-%m-%d')}")

    if date_object == original_date:
        cache_data = {"text": text, "date": date_object.strftime("%Y-%m-%d")}
        ttl = await get_ttl()
        await redis_client.setex(cache_key, ttl, json.dumps(cache_data))
        logger.debug(f"Cached homework for user {user_id}, key: {cache_key}, TTL: {ttl}")

    logger.info(f"Homework retrieved for user {user_id}, {homework_count} tasks on {date_object.strftime('%Y-%m-%d')}")
    return text, date_object



@handle_api_error()
async def get_homework_by_subject(user_id, subject_id, date_object):
    logger.info(f"Getting homework by subject for user {user_id}, subject_id: {subject_id}, week starting: {date_object.strftime('%Y-%m-%d')}")
    
    date_object = date_object - timedelta(days=date_object.weekday())

    cache_key = f"homework_subject:{user_id}:{subject_id}:{date_object.strftime('%Y-%m-%d')}"

    cache_redis = await redis_client.get(cache_key)
    if cache_redis:
        logger.debug(f"Cache hit for subject homework: user {user_id}, subject {subject_id}")
        return cache_redis

    api, user = await get_student(user_id)
    if not api or not user:
        logger.error(f"Failed to get student data for user {user_id}")
        return f'❌ <b>Ошибка</b>\n\nНе удалось получить данные ученика'

    cache = temp_events.get(user_id)

    now = datetime.now()
    begin_date = date_object
    end_date = date_object + timedelta(days=6)

    if (
        cache is not None
        and cache["timestamp"] + timedelta(hours=1) > now
        and cache["begin_date"] <= begin_date
        and cache["end_date"] >= end_date
    ):
        homeworks = cache["data"]
        logger.debug(f"Using temp cache for user {user_id}, found {len(homeworks.payload)} homeworks")

    else:
        logger.debug(f"Fetching homeworks from API for week {begin_date.strftime('%Y-%m-%d')} - {end_date.strftime('%Y-%m-%d')}")
        homeworks = await api.get_homeworks(
            student_id=user.student_id,
            profile_id=user.profile_id,
            from_date=begin_date,
            to_date=end_date,
        )

        temp_events[user_id] = {
            "data": homeworks,
            "timestamp": now,
            "begin_date": begin_date,
            "end_date": end_date,
        }
        logger.debug(f"Updated temp cache for user {user_id}")

    if not homeworks or not homeworks.payload:
        logger.warning(f"No homework data for user {user_id} in specified week")
        return f'❌ <b>Нет домашних заданий</b>\n\nЗа указанную неделю нет данных'
    
    # Сбор данных по предмету
    subject_name = ""
    homeworks_list = []
    total_for_subject = 0

    sorted_homeworks = sorted(homeworks.payload, key=lambda x: x.date_prepared_for)

    for homework in sorted_homeworks:
        if homework.subject_id == subject_id:
            total_for_subject += 1
            subject_name = homework.subject_name

            materials = []

            for material in homework.materials:
                try:
                    if len(material.urls) != 0:
                        for url in material.urls:
                            materials.append(
                                {
                                    "url": url.url,
                                    "title": material.title,
                                    "material_type_name": material.type_name,
                                    "material_type": material.type,
                                }
                            )
                    else:
                        activity_url = await api.get_activity_launch_link(
                            homework_entry_id=homework.homework_entry_id,
                            material_id=material.uuid,
                        )
                        materials.append(
                            {
                                "url": activity_url,
                                "title": material.title,
                                "material_type_name": material.type_name,
                                "material_type": material.type,
                            }
                        )
                except Exception as e:
                    logger.error(f"Error processing material for homework {homework.homework_entry_id}: {e}")

            homeworks_list.append(
                {
                    "homework": homework.homework,
                    "materials": materials,
                    "date": homework.lesson_date_time,
                    "homework_entry_id": homework.homework_entry_id,
                }
            )
            
    logger.debug(f"Found {total_for_subject} homework entries for subject {subject_id}")

    if not subject_name:
        logger.debug(f"Subject name not found in homework data, fetching from subjects list")
        subjects = await api.get_subjects(
            student_id=user.student_id, profile_id=user.profile_id
        )
        subject_name = next(
            (
                subject.subject_name
                for subject in subjects.payload
                if subject.subject_id == subject_id
            ),
            None,
        )

    # Формирование текста
    text = f"{await get_emoji_subject(subject_name)} <b>{subject_name}</b> {begin_date.strftime("%d %b")} – {end_date.strftime("%d %b")}\n\n"

    days_with_homework = 0
    days_without_homework = 0

    for homework in homeworks_list:
        if homework["homework"] or len(homework["materials"]) > 0:
            days_with_homework += 1
            text += f"📅 <b>{homework['date'].strftime('%d %B (%a)')}:</b>\n"
            if homework["homework"]:
                task = homework["homework"]

                # Работа с БД для домашнего задания
                async with await get_session() as session:
                    result = await session.execute(
                        db.select(Homework).filter_by(task=task, subject_id=subject_id)
                    )
                    homework_db = result.scalar_one_or_none()
                    if not homework_db:
                        homework_db = Homework(task=task, subject_id=subject_id)
                        session.add(homework_db)
                        await session.commit()
                        await session.refresh(homework_db)
                        logger.debug(f"Created new Homework record for task: {task[:50]}...")

                text += f"    📚 <b>Домашние задание:</b>\n"
                if LEARNIFY_API_TOKEN:
                    gdz_link = (
                        f'<a href="{await generate_deeplink(f'autogdz-{homework_db.id}')}">⚡</a>'
                        if await has_numbers(task)
                        else ""
                    )
                    text += f"        - {f'<code>{task}</code>' if 'https://' not in task else f'<i>{task}</i>'} {gdz_link}\n"
                else:
                    text += f"        - {f'<code>{task}</code>' if 'https://' not in task else f'<i>{task}</i>'}\n"

            if len(homework["materials"]) > 0:
                text += f"\n    🔗 <b>Для выполнения:</b>\n"
                for material in homework["materials"]:
                    text += f'        - <a href="{material["url"]}">{material["title"]} ({material["material_type_name"]})</a>\n'
                    logger.debug(f"Added material link: {material['title']}")

            text += "\n"
        else:
            days_without_homework += 1
            text += f"📅 <b>{homework['date'].strftime('%d %B (%a)')}:</b>\n"
            text += f"    ❌ <b>Нет домашних заданий</b>\n"
            text += "\n"

    if len(homeworks_list) == 0:
        text += f"❌ <b>У вас нет домашних заданий по предмету</b>"
        logger.info(f"No homework entries for subject {subject_id} in week {begin_date.strftime('%Y-%m-%d')}")
    else:
        logger.info(f"Subject homework formatted: {days_with_homework} days with homework, {days_without_homework} without")

    await redis_client.setex(cache_key, DEFAULT_SHORT_CACHE_TTL, text)
    logger.debug(f"Cached subject homework for user {user_id}, key: {cache_key}, TTL: {DEFAULT_SHORT_CACHE_TTL}")

    return text


async def handle_homework_navigation(
    user_id: int,
    state: FSMContext,
    direction: str = None,
    subject_mode: bool = False,
    date: datetime = None,
    subject_id=None,
):
    logger.info(f"Handling homework navigation for user {user_id}, direction={direction}, subject_mode={subject_mode}")
    
    data = await state.get_data()

    if not date:
        date = data.get("date", datetime.now())
        logger.debug(f"Current date from state: {date.strftime('%Y-%m-%d')}")
        
        if direction == "left":
            date -= timedelta(days=7 if subject_mode else 1)
            logger.debug(f"Moving left: new date {date.strftime('%Y-%m-%d')}")
        elif direction == "right":
            date += timedelta(days=7 if subject_mode else 1)
            logger.debug(f"Moving right: new date {date.strftime('%Y-%m-%d')}")
        elif direction == "to_date":
            date = date
            logger.debug(f"Using provided date: {date.strftime('%Y-%m-%d')}")
        else:  # today
            date = datetime.now()
            logger.debug(f"Moving to today: {date.strftime('%Y-%m-%d')}")

    if subject_mode:
        subject_id = subject_id or data.get("subject_id")
        if not subject_id:
            logger.warning(f"No subject_id for subject mode, showing subject choice")
            return None, date, await kb.choice_subject(user_id, "homework")

        logger.debug(f"Getting homework by subject {subject_id} for week starting {date.strftime('%Y-%m-%d')}")
        text = await get_homework_by_subject(user_id, subject_id, date)
        markup = kb.subject_homework
    else:
        logger.debug(f"Getting homework for date {date.strftime('%Y-%m-%d')}")
        text, date = await get_homework(user_id, date, direction)
        markup = kb.homework

    logger.info(f"Homework navigation successful for user {user_id}")
    return text, date, markup
