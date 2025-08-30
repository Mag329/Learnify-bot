from datetime import datetime, timedelta

from app.utils.database import AsyncSessionLocal, BotNotification, db
from app.utils.user.utils import EMOJI_NUMBERS, get_emoji_subject, get_student


async def get_replaces(user_id, date_object):
    try:
        api, user = await get_student(user_id)

        schedule = await api.get_events(
            person_id=user.person_id,
            mes_role=user.role,
            begin_date=date_object,
            end_date=date_object,
        )

        text = f'🔄 <b>Замены на</b> {date_object.strftime("%d %B (%a)")}:\n\n'
        have_replaced = False

        for num, event in enumerate(schedule.response, 1):
            if event.replaced:
                have_replaced = True

                lesson_info = await api.get_lesson_schedule_item(
                    profile_id=user.profile_id,
                    lesson_id=event.id,
                    student_id=user.student_id,
                    type=event.source,
                )

                text += f'{EMOJI_NUMBERS.get(num, f"{num}️")} {await get_emoji_subject(event.subject_name)} <b>{event.subject_name}</b>\n     👤<i>{lesson_info.teacher.first_name[0]}. {lesson_info.teacher.middle_name[0]}. {lesson_info.teacher.last_name}</i>\n\n'

        async with AsyncSessionLocal() as session:
            result = await session.execute(
                db.select(BotNotification).filter(
                    BotNotification.user_id == user_id,
                    BotNotification.created_at < datetime.now() - timedelta(days=1),
                )
            )
            for notification in result.scalars().all():
                await session.delete(notification)
                await session.commit()

            if have_replaced:
                result: BotNotification = await session.execute(
                    db.select(BotNotification).filter_by(
                        user_id=user_id, text=text, type="replaced"
                    )
                )
                notifications = result.scalars().all()

                if not notifications:
                    notification = BotNotification(
                        user_id=user_id, type="replaced", text=text
                    )
                    session.add(notification)
                    await session.commit()

                    return text

            else:
                return f'❌ <b>Нет замен на </b>{date_object.strftime("%d %B (%a)")}'
    except:
        pass
