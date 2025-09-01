import asyncio
from datetime import datetime, timedelta, timezone

from aiogram.fsm.context import FSMContext
from aiogram.types import Message

import app.keyboards.user.keyboards as kb
from app.states.user.states import ScheduleState
from app.utils.database import AsyncSessionLocal, Settings, db
from app.utils.user.decorators import handle_api_error
from app.utils.user.utils import EMOJI_NUMBERS, get_emoji_subject, get_student

# Словарь для хранения задач пользователей
user_tasks = {}


@handle_api_error()
async def get_schedule(user_id, date_object, short=True, direction="right"):
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
        and short
        and settings.next_day_if_lessons_end_schedule
    ):
        date_object += timedelta(days=1)
        schedule = await api.get_events(
            person_id=user.person_id,
            mes_role=user.role,
            begin_date=date_object,
            end_date=date_object,
        )

    if settings.skip_empty_days_schedule and short:
        lessons_count = 0
        empty_days = 0

        while lessons_count <= 0 and empty_days <= 14:
            schedule = await api.get_events(
                person_id=user.person_id,
                mes_role=user.role,
                begin_date=date_object,
                end_date=date_object,
            )
            lessons_count = schedule.total_count
            if lessons_count <= 0:
                empty_days += 1
                if direction in ["right", "today"]:
                    date_object += timedelta(days=1)  # Переход вправо
                else:
                    date_object -= timedelta(days=1)  # Переход влево
            else:
                empty_days = 0
                
        if empty_days > 14:
            schedule = await api.get_events(
                person_id=user.person_id,
                mes_role=user.role,
                begin_date=original_date,
                end_date=original_date,
            )
            date_object = original_date
            

    text = f'📅 <b>Расписание на</b> {date_object.strftime("%d %B (%a)")}:\n\n'

    for num, event in enumerate(schedule.response, 1):
        start_time = event.start_at.strftime("%H:%M")
        end_time = event.finish_at.strftime("%H:%M")

        if not short:
            lesson_info = await api.get_lesson_schedule_item(
                profile_id=user.profile_id,
                lesson_id=event.id,
                student_id=user.student_id,
                type=event.source,
            )

            text += f'{EMOJI_NUMBERS.get(num, f"{num}️")} {await get_emoji_subject(event.subject_name)} <b>{event.subject_name}</b> <i>({start_time}-{end_time})</i> {" <code>Н</code>" if event.is_missed_lesson else ""} {" 🟢" if event.start_at < datetime.now(timezone.utc) and datetime.now(timezone.utc) < event.finish_at else ""}\n    📍 {event.room_number}\n    👤 <i>{lesson_info.teacher.first_name[0]}. {lesson_info.teacher.middle_name[0]}. {lesson_info.teacher.last_name}</i> {" - 🔄 замена" if event.replaced else ""}\n\n'
        else:
            replaced_text = "\n    👤 - 🔄 замена"
            text += f'{EMOJI_NUMBERS.get(num, f"{num}️")} {await get_emoji_subject(event.subject_name)} <b>{event.subject_name}</b> <i>({start_time}-{end_time})</i> {" <code>Н</code>" if event.is_missed_lesson else ""} {" 🟢" if event.start_at < datetime.now(timezone.utc) and datetime.now(timezone.utc) < event.finish_at else ""}\n    📍 {event.room_number}{replaced_text if event.replaced else ""}\n\n'

    return text, date_object


async def update_detailed_schedule(message: Message, user_id: int, date: datetime):
    detailed_schedule, new_date = await get_schedule(user_id, date, False)
    if detailed_schedule:
        if message.html_text != detailed_schedule:
            await message.edit_text(detailed_schedule, reply_markup=kb.schedule)


async def cancel_previous_task(user_id: int):
    if user_id in user_tasks:
        task = user_tasks[user_id]
        if not task.done():
            task.cancel()


async def handle_schedule_navigation(
    user_id: int,
    message: Message,
    state: FSMContext,
    direction: str,
):
    data = await state.get_data()
    date = data.get("date", datetime.now())

    if direction == "left":
        date -= timedelta(days=1)
    elif direction == "right":
        date += timedelta(days=1)
    else:  # "today"
        date = datetime.now()

    text, new_date = await get_schedule(user_id, date, direction)
    await state.set_state(ScheduleState.date)
    await state.update_data(date=new_date)

    if text:
        await message.edit_text(text, reply_markup=kb.schedule)

        # Перезапуск отложенной задачи
        await cancel_previous_task(user_id)
        user_tasks[user_id] = asyncio.create_task(
            update_detailed_schedule(message, user_id, new_date)
        )
