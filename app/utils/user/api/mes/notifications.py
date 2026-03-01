# SPDX-FileCopyrightText: 2024-2026 Mag329
#
# SPDX-License-Identifier: MIT

import asyncio
from loguru import logger

from octodiary.exceptions import APIError

from app.keyboards import user as kb
from app.config.config import ERROR_403_MESSAGE, ERROR_MESSAGE
from app.utils.database import get_session, Event, Settings, db
from app.utils.user.cache import invalidate_cache_for_notification
from app.utils.user.utils import (
    get_emoji_subject,
    get_mark_with_weight,
    get_student,
    user_send_message,
)


async def get_notifications(user_id, all=True, is_checker=False):
    log_msg = f"Getting notifications for user {user_id}, all={all}, is_checker={is_checker}"
    if is_checker:
        logger.debug(log_msg)
    else:
        logger.info(log_msg)
    
    try:
        logger.debug(f"Fetching student data for user {user_id}")
        api, user = await get_student(user_id)
        
        if not user:
            logger.warning(f"User {user_id} not authenticated")
            if is_checker:
                return None
            await user_send_message(user_id, "❌ <b>Вы не авторизованы</b>", kb.reauth)
            return None

        logger.debug(f"Fetching notifications from API for user {user_id}")
        notifications = await api.get_notifications(
            student_id=user.student_id, profile_id=user.profile_id
        )

        if not notifications:
            logger.info(f"No notifications found for user {user_id}")
            return None if is_checker else "❌ <b>У вас нет уведомлений</b>"
        
        logger.debug(f"Retrieved {len(notifications)} notifications from API")

        async with await get_session() as session:
            logger.debug(f"Fetching settings for user {user_id}")
            settings = (
                await session.execute(
                    db.select(Settings).filter(Settings.user_id == user_id)
                )
            ).scalar_one_or_none()

            logger.debug(f"Fetching existing events for student {notifications[0].student_profile_id}")
            
            events = (
                (
                    await session.execute(
                        db.select(Event).filter(
                            Event.student_id == notifications[0].student_profile_id
                        )
                    )
                )
                .scalars()
                .all()
            )

            existing = {(e.teacher_id, e.event_type, e.date) for e in events}
            logger.debug(f"Found {len(existing)} existing events")

            new_notifications = []
            cache_invalidation_tasks = []
            new_events_count = 0

            for n in notifications:
                key = (n.author_profile_id, n.event_type, n.created_at)
                if key not in existing:
                    new_notifications.append(n)
                    session.add(
                        Event(
                            student_id=n.student_profile_id,
                            event_type=n.event_type,
                            subject_name=n.subject_name,
                            date=n.created_at,
                            teacher_id=n.author_profile_id,
                        )
                    )
                    new_events_count += 1
                    cache_invalidation_tasks.append(
                        invalidate_cache_for_notification(user_id, n)
                    )

            logger.debug(f"Found {new_events_count} new notifications to save")
            await session.commit()
            
            if cache_invalidation_tasks:
                for task in cache_invalidation_tasks:
                    asyncio.create_task(task)

        if not all:
            notifications = new_notifications
            logger.debug(f"Filtered to only new notifications: {len(notifications)}")

        if not notifications:
            msg_log = f"No {'new' if not all else ''} notifications for user {user_id}"
            if is_checker:
                logger.debug(msg_log)
            else:
                logger.info(msg_log)
            return None if is_checker else "❌ <b>У вас нет новых уведомлений</b>"

        # Настройки фильтрации
        event_filter = {
            "create_mark": settings.enable_new_mark_notification,
            "update_mark": settings.enable_new_mark_notification,
            "delete_mark": settings.enable_new_mark_notification,
            "create_homework": settings.enable_homework_notification,
            "update_homework": settings.enable_homework_notification,
        }

        filtered = [
            n
            for n in notifications
            if (not is_checker or event_filter.get(n.event_type, False))
        ]

        if not filtered:
            logger.info(f"All notifications filtered out for user {user_id}")
            return None if is_checker else "❌ <b>У вас нет новых уведомлений</b>"

        text = f"🔔 <b>Уведомления ({len(filtered)}):</b>\n\n"
        processed_types = {}

        for n in filtered:
            time = n.created_at.strftime("%d.%m %H:%M")
            subject = f"{await get_emoji_subject(n.subject_name)} {n.subject_name} ({time})\n        "

            if n.event_type == "create_mark":
                detail = f"<b>Новая оценка:</b>\n            <i><code>{await get_mark_with_weight(n.new_mark_value, n.new_mark_weight)} - {n.control_form_name}</code></i>"
                processed_types["create_mark"] = processed_types.get("create_mark", 0) + 1
            elif n.event_type == "update_mark":
                detail = f"<b>Изменение оценки:</b>\n            <i><code>{await get_mark_with_weight(n.old_mark_value, n.old_mark_weight)} -> {await get_mark_with_weight(n.new_mark_value, n.new_mark_weight)} - {n.control_form_name}</code></i>"
                processed_types["update_mark"] = processed_types.get("update_mark", 0) + 1
            elif n.event_type == "delete_mark":
                detail = f"<b>Удаление оценки:</b>\n            <i><code>{await get_mark_with_weight(n.old_mark_value, n.old_mark_weight)} - {n.control_form_name}</code></i>"
                processed_types["delete_mark"] = processed_types.get("delete_mark", 0) + 1
            elif n.event_type in {"create_homework", "update_homework"}:
                action = (
                    "Новое домашние задание"
                    if n.event_type == "create_homework"
                    else "Изменение домашних задания"
                )
                detail = f"<b>{action}:</b>\n            <i><code>{n.new_hw_description.rstrip()}</code></i>"
                processed_types[n.event_type] = processed_types.get(n.event_type, 0) + 1
            else:
                logger.debug(f"Skipping unknown event type: {n.event_type}")
                continue

            text += f"{subject}{detail}\n\n"

        logger.info(f"Generated notifications for user {user_id}: {len(filtered)} total, types: {processed_types}")
        return text

    except APIError as e:
        logger.error(f"APIError ({e.status_code}) for user {user_id} in get_notifications: {e}")
        if not is_checker:
            msg = ERROR_403_MESSAGE if e.status_code in [401, 403] else ERROR_MESSAGE
            await user_send_message(
                user_id,
                msg,
                kb.reauth if e.status_code in [401, 403] else kb.delete_message,
            )
        return None
    
    except Exception as e:
        logger.exception(f"Unexpected error in get_notifications for user {user_id}: {e}")
        if not is_checker:
            await user_send_message(user_id, ERROR_MESSAGE, kb.delete_message)
        return None
