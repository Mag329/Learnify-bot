from datetime import datetime, timedelta, timezone

from aiogram.fsm.context import FSMContext

import app.keyboards.user.keyboards as kb
from app.utils.database import AsyncSessionLocal, Settings, db
from app.utils.user.decorators import handle_api_error
from app.utils.user.utils import get_emoji_subject, get_student

# Temp dicts
temp_events = {}


@handle_api_error()
async def get_homework(user_id, date_object, direction="right"):
    api, user = await get_student(user_id)

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
        homework = await api.get_homeworks_short(
            student_id=user.student_id,
            profile_id=user.profile_id,
            from_date=date_object,
            to_date=date_object,
        )

    if settings.skip_empty_days_homeworks:
        homework_count = 0
        empty_days = 0

        while homework_count <= 0 and empty_days <= 14:
            homework = await api.get_homeworks_short(
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

    else:
        homework = await api.get_homeworks_short(
            student_id=user.student_id,
            profile_id=user.profile_id,
            from_date=date_object,
            to_date=date_object,
        )

    text = f'📚 <b>Домашние задания на</b> {date_object.strftime("%d %B (%a)")}:\n\n'

    for task in homework.payload:
        description = task.description.rstrip("\n")
        materials = (
            f"<i> (Для выполнения: {task.materials_count[0].amount})</i>"
            if len(task.materials_count) > 0
            else ""
        )
        text += f"{await get_emoji_subject(task.subject_name)} <b>{task.subject_name}</b>{materials}<b>:</b>\n    <code>{description}</code>\n\n"

    if len(homework.payload) == 0:
        text = f'❌ <b>У вас нет домашних заданий на </b>{date_object.strftime("%d %B (%a)")}'

    return text, date_object


@handle_api_error()
async def get_homework_by_subject(user_id, subject_id, date_object):
    api, user = await get_student(user_id)

    cache = temp_events.get(user_id)

    now = datetime.now()
    begin_date = date_object
    end_date = date_object + timedelta(days=7)

    if (
        cache is not None
        and cache["timestamp"] + timedelta(hours=1) > now
        and cache["begin_date"] <= begin_date
        and cache["end_date"] >= end_date
    ):
        events = cache["data"]

    else:
        events = await api.get_events(
            person_id=user.person_id,
            mes_role=user.role,
            begin_date=date_object,
            end_date=date_object + timedelta(days=7),
        )

        temp_events[user_id] = {
            "data": events,
            "timestamp": now,
            "begin_date": begin_date,
            "end_date": end_date,
        }

    subject_name = ""
    homeworks = []

    for event in events.response:
        if event.subject_id == subject_id:
            lesson_info = await api.get_lesson_schedule_item(
                profile_id=user.profile_id,
                student_id=user.student_id,
                lesson_id=event.id,
                type=event.source,
            )

            subject_name = lesson_info.subject_name

            materials = []

            for homework in lesson_info.lesson_homeworks:
                for material in homework.materials:
                    # if material.type in ['test_spec_binding', 'game_app', 'workbook', '']:
                    for item in material.items:
                        for url in item.urls:
                            if url.url_type == "launch":
                                materials.append(
                                    {
                                        "url": url.url,
                                        "title": item.title,
                                        "material_type_name": material.type_name,
                                        "material_type": material.type,
                                    }
                                )

            homeworks.append(
                {
                    "homeworks": lesson_info.lesson_homeworks,
                    "materials": materials,
                    "date": lesson_info.date,
                    "lesson_id": lesson_info.id,
                }
            )

    text = f"{await get_emoji_subject(subject_name)} <b>{subject_name}</b>\n\n"

    for homework in homeworks:
        if len(homework["homeworks"]) > 0 or len(homework["materials"]) > 0:
            text += f"📅 <b>{homework['date'].strftime('%d %B (%a)')}:</b>\n"
            if len(homework["homeworks"]) > 0:
                text += f"    📚 <b>Домашние задание:</b>\n"
                for task in homework["homeworks"]:
                    text += f"        - <i><code>{task.homework}</code></i>\n"

            if len(homework["materials"]) > 0:
                text += f"\n    🔗 <b>Для выполнения:</b>\n"
                for material in homework["materials"]:
                    text += f'        - <a href="{material["url"]}">{material["title"]} ({material["material_type_name"]})</a>\n'

            text += "\n"
        else:
            text += f"📅 <b>{homework['date'].strftime('%d %B (%a)')}:</b>\n"
            text += f"    ❌ <b>Нет домашних заданий</b>\n"
            text += "\n"

    return text


async def handle_homework_navigation(
    user_id: int,
    state: FSMContext,
    direction: str,
    subject_mode: bool = False,
):
    data = await state.get_data()
    date = data.get("date", datetime.now())

    if direction == "left":
        date -= timedelta(days=7 if subject_mode else 1)
    elif direction == "right":
        date += timedelta(days=7 if subject_mode else 1)
    else:  # today
        date = datetime.now()

    await state.update_data(date=date)

    if subject_mode:
        subject_id = data.get("subject_id")
        if not subject_id:
            return None, await kb.choice_subject(user_id, "homework")
        text = await get_homework_by_subject(user_id, subject_id, date)
        markup = kb.subject_homework
    else:
        text, _ = await get_homework(user_id, date, direction)
        markup = kb.homework

    return text, markup
