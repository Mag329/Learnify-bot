# SPDX-FileCopyrightText: 2024-2026 Mag329
#
# SPDX-License-Identifier: MIT

from datetime import datetime, timedelta
from loguru import logger

from app.utils.database import get_session, BotNotification, db
from app.utils.user.utils import EMOJI_NUMBERS, get_emoji_subject, get_student


async def get_replaces(user_id, date_object):
    logger.info(f"Getting replaces for user {user_id}, date: {date_object.strftime('%Y-%m-%d')}")
    
    api, user = await get_student(user_id)
    if not api or not user:
        logger.error(f"Failed to get student data for user {user_id}")
        return None

    logger.debug(f"Fetching schedule for {date_object.strftime('%Y-%m-%d')}")
    schedule = await api.get_events(
        person_id=user.person_id,
        mes_role=user.role,
        begin_date=date_object,
        end_date=date_object,
    )

    text = f'🔄 <b>Замены на</b> {date_object.strftime("%d %B (%a)")}:\n\n'
    have_replaced = False
    replaced_count = 0

    for num, event in enumerate(schedule.response, 1):
        if event.replaced:
            have_replaced = True
            replaced_count += 1
            logger.debug(f"Found replaced lesson #{num}: {event.subject_name}")

            lesson_info = await api.get_lesson_schedule_item(
                profile_id=user.profile_id,
                lesson_id=event.id,
                student_id=user.student_id,
                type=event.source,
            )

            text += f'{EMOJI_NUMBERS.get(num, f"{num}️")} {await get_emoji_subject(event.subject_name)} <b>{event.subject_name}</b>\n     👤<i>{lesson_info.teacher.first_name[0]}. {lesson_info.teacher.middle_name[0]}. {lesson_info.teacher.last_name}</i>\n\n'

    logger.debug("Cleaning old notifications")
    async with await get_session() as session:
        try:
            result = await session.execute(
                db.select(BotNotification).filter(
                    BotNotification.user_id == user_id,
                    BotNotification.created_at < datetime.now() - timedelta(days=1),
                )
            )
            for notification in result.scalars().all():
                await session.delete(notification)
                await session.commit()
        except Exception as e:
            logger.error(f"Error cleaning old notifications: {e}")

        if have_replaced:
            logger.info(f"Found {replaced_count} replacements for user {user_id}")
            
            
            try:
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
            except Exception as e:
                logger.error(f"Error saving replacement notification: {e}")
                return text

        else:
            logger.info(f"No replacements found for user {user_id} on {date_object.strftime('%Y-%m-%d')}")
            return f'❌ <b>Нет замен на </b>{date_object.strftime("%d %B (%a)")}'
