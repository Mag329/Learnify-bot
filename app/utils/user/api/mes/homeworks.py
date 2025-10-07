import json
from datetime import datetime, timedelta, timezone

from aiogram.fsm.context import FSMContext

import app.keyboards.user.keyboards as kb
from app.config import config
from app.config.config import DEFAULT_SHORT_CACHE_TTL
from app.utils.database import AsyncSessionLocal, Settings, db
from app.utils.user.cache import get_ttl, redis_client
from app.utils.user.decorators import cache, cache_text_only, handle_api_error
from app.utils.user.utils import get_emoji_subject, get_student

# Temp dicts
temp_events = {}


@handle_api_error()
async def get_homework(user_id, date_object, direction="right"):
    async with AsyncSessionLocal() as session:
        result = await session.execute(db.select(Settings).filter_by(user_id=user_id))
        settings: Settings = result.scalar_one_or_none()

    use_cache = settings and settings.experimental_features and settings.use_cache
    cache_key = f"homeworks:{user_id}:{date_object.strftime('%Y-%m-%d')}:{direction if direction != 'to_date' else 'today'}"
    
    # Чтение кэша только если это не "to_date"
    if use_cache and direction != 'to_date':
        cached_full = await redis_client.get(cache_key)
        if cached_full:
            data = json.loads(cached_full)
            return data["text"], datetime.strptime(data["date"], "%Y-%m-%d")

    api, user = await get_student(user_id)

    original_date = date_object

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            db.select(Settings).filter(Settings.user_id == user_id)
        )
        settings: Settings = result.scalar_one_or_none()

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
        and settings.next_day_if_lessons_end_homeworks
    ):
        date_object += timedelta(days=1)
        homework = await api.get_homeworks(
            student_id=user.student_id,
            profile_id=user.profile_id,
            from_date=date_object,
            to_date=date_object,
        )

    if settings.skip_empty_days_homeworks and direction != "to_date":
        homework_count = 0
        empty_days = 0

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
            else:
                empty_days = 0

        if empty_days > 14:
            homework = await api.get_homeworks(
                student_id=user.student_id,
                profile_id=user.profile_id,
                from_date=original_date,
                to_date=original_date,
            )
            date_object = original_date

    else:
        homework = await api.get_homeworks(
            student_id=user.student_id,
            profile_id=user.profile_id,
            from_date=date_object,
            to_date=date_object,
        )

    text = f'📚 <b>Домашние задания на</b> {date_object.strftime("%d %B (%a)")}:\n\n'
    sorted_homeworks = sorted(homework.payload, key=lambda x: x.subject_name)

    for task in sorted_homeworks:
        description = task.description.rstrip("\n")
        materials_amount = sum(1 for m in task.materials if m.type not in ["attachments"])
        materials = f"<i> (Для выполнения: {materials_amount})</i>" if materials_amount else ""
        description_code = f"<code>{description}</code>" if "https://" not in description else f"<i>{description}</i>"
        is_done = task.is_done

        if settings.enable_homework_done_function:
            link = f'<a href="https://t.me/{config.BOT_USERNAME}?start=done-homework-{task.homework_entry_student_id}-{"True" if not is_done else "False"}">'
            link += "◼️</a>" if not is_done else "✔️</a>"
            description_text = f"<s>{description}</s>" if is_done else description_code
        else:
            link = ""
            description_text = description_code

        subject_name = f'{await get_emoji_subject(task.subject_name)} <b>{task.subject_name}</b>{materials}'
        subject_name_with_link = f'<a href="https://t.me/{config.BOT_USERNAME}?start=subject-homework-{task.subject_id}-{task.date_prepared_for.strftime("%d_%m_%Y")}">{subject_name}</a>'
        
        text += f"{subject_name_with_link}<b>:</b>\n    {link} {description_text}\n\n"

    if len(homework.payload) == 0:
        text = f'❌ <b>У вас нет домашних заданий на </b>{date_object.strftime("%d %B (%a)")}'

    if date_object == original_date and use_cache:
        cache_data = {"text": text, "date": date_object.strftime("%Y-%m-%d")}
        ttl = await get_ttl()
        await redis_client.setex(cache_key, ttl, json.dumps(cache_data))

    return text, date_object


@handle_api_error()
async def get_homework_by_subject(user_id, subject_id, date_object):
    date_object = date_object - timedelta(days=date_object.weekday())

    async with AsyncSessionLocal() as session:
        result = await session.execute(db.select(Settings).filter_by(user_id=user_id))
        settings: Settings = result.scalar_one_or_none()
        if settings and settings.experimental_features and settings.use_cache:
            cache_key = f"homework_subject:{user_id}:{subject_id}:{date_object.strftime('%Y-%m-%d')}"

            cache_redis = await redis_client.get(cache_key)
            if cache_redis:
                return cache_redis

            use_cache = True
        else:
            use_cache = False

    api, user = await get_student(user_id)

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

    else:
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

    subject_name = ""
    homeworks_list = []
    
    sorted_homeworks = sorted(homeworks.payload, key=lambda x: x.date_prepared_for)

    for homework in sorted_homeworks:
        if homework.subject_id == subject_id:
            subject_name = homework.subject_name

            materials = []

            for material in homework.materials:
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

            homeworks_list.append(
                {
                    "homework": homework.homework,
                    "materials": materials,
                    "date": homework.lesson_date_time,
                    "homework_entry_id": homework.homework_entry_id,
                }
            )

    if not subject_name:
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

    text = f"{await get_emoji_subject(subject_name)} <b>{subject_name}</b> {begin_date.strftime("%d %b")} – {end_date.strftime("%d %b")}\n\n"

    for homework in homeworks_list:
        if homework["homework"] or len(homework["materials"]) > 0:
            text += f"📅 <b>{homework['date'].strftime('%d %B (%a)')}:</b>\n"
            if homework["homework"]:
                task = homework['homework']
                text += f"    📚 <b>Домашние задание:</b>\n"
                text += f"        - {f'<code>{task}</code>' if 'https://' not in task else f'<i>{task}</i>'}\n"

            if len(homework["materials"]) > 0:
                text += f"\n    🔗 <b>Для выполнения:</b>\n"
                for material in homework["materials"]:
                    text += f'        - <a href="{material["url"]}">{material["title"]} ({material["material_type_name"]})</a>\n'

            text += "\n"
        else:
            text += f"📅 <b>{homework['date'].strftime('%d %B (%a)')}:</b>\n"
            text += f"    ❌ <b>Нет домашних заданий</b>\n"
            text += "\n"

    if len(homeworks_list) == 0:
        text += f"❌ <b>У вас нет домашних заданий по предмету</b>"

    if use_cache:
        await redis_client.setex(cache_key, DEFAULT_SHORT_CACHE_TTL, text)

    return text


async def handle_homework_navigation(
    user_id: int,
    state: FSMContext,
    direction: str = None,
    subject_mode: bool = False,
    date: datetime = None,
    subject_id=None
):
    data = await state.get_data()

    if not date:
        date = data.get("date", datetime.now())
        if direction == "left":
            date -= timedelta(days=7 if subject_mode else 1)
        elif direction == "right":
            date += timedelta(days=7 if subject_mode else 1)
        elif direction == "to_date":
            date = date
        else:  # today
            date = datetime.now()


    if subject_mode:
        subject_id = subject_id or data.get("subject_id")
        if not subject_id:
            return None, date, await kb.choice_subject(user_id, "homework")

        text = await get_homework_by_subject(user_id, subject_id, date)
        markup = kb.subject_homework
    else:
        text, date = await get_homework(user_id, date, direction)
        markup = kb.homework

    return text, date, markup
