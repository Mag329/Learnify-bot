import asyncio
import logging

from octodiary.exceptions import APIError

import app.keyboards.user.keyboards as kb
from app.config.config import ERROR_403_MESSAGE, ERROR_MESSAGE
from app.utils.database import AsyncSessionLocal, Event, Settings, db
from app.utils.user.cache import invalidate_cache_for_notification
from app.utils.user.utils import (get_emoji_subject, get_mark_with_weight,
                                  get_student, user_send_message)

logger = logging.getLogger(__name__)


async def get_notifications(user_id, all=True, is_checker=False):
    try:
        api, user = await get_student(user_id)
        if not user:
            if is_checker:
                return None
            await user_send_message(user_id, "❌ <b>Вы не авторизованы</b>", kb.reauth)
            return None

        notifications = await api.get_notifications(
            student_id=user.student_id, profile_id=user.profile_id
        )

        if not notifications:
            return None if is_checker else "❌ <b>У вас нет уведомлений</b>"

        async with AsyncSessionLocal() as session:
            settings = (
                await session.execute(
                    db.select(Settings).filter(Settings.user_id == user_id)
                )
            ).scalar_one_or_none()

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

            new_notifications = []
            cache_invalidation_tasks = []

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
                    cache_invalidation_tasks.append(
                        invalidate_cache_for_notification(user_id, n)
                    )

            await session.commit()
            if cache_invalidation_tasks:
                for task in cache_invalidation_tasks:
                    asyncio.create_task(task)

        if not all:
            notifications = new_notifications

        if not notifications:
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
            return None if is_checker else "❌ <b>У вас нет новых уведомлений</b>"

        text = f"🔔 <b>Уведомления ({len(filtered)}):</b>\n\n"

        for n in filtered:
            time = n.created_at.strftime("%d.%m %H:%M")
            subject = f"{await get_emoji_subject(n.subject_name)} {n.subject_name} ({time})\n        "

            if n.event_type == "create_mark":
                detail = f"<b>Новая оценка:</b>\n            <i><code>{await get_mark_with_weight(n.new_mark_value, n.new_mark_weight)} - {n.control_form_name}</code></i>"
            elif n.event_type == "update_mark":
                detail = f"<b>Изменение оценки:</b>\n            <i><code>{n.old_mark_value} -> {await get_mark_with_weight(n.new_mark_value, n.new_mark_weight)} - {n.control_form_name}</code></i>"
            elif n.event_type == "delete_mark":
                detail = f"<b>Удаление оценки:</b>\n            <i><code>{n.old_mark_value} - {n.control_form_name}</code></i>"
            elif n.event_type in {"create_homework", "update_homework"}:
                action = (
                    "Новое домашние задание"
                    if n.event_type == "create_homework"
                    else "Изменение домашних задания"
                )
                detail = f"<b>{action}:</b>\n            <i><code>{n.new_hw_description.rstrip()}</code></i>"
            else:
                continue

            text += f"{subject}{detail}\n\n"

        return text

    except APIError as e:
        if not is_checker:
            msg = ERROR_403_MESSAGE if e.status_code in [401, 403] else ERROR_MESSAGE
            await user_send_message(
                user_id,
                msg,
                kb.reauth if e.status_code in [401, 403] else kb.delete_message,
            )
    except Exception as e:
        logger.error(e)
        if not is_checker:
            await user_send_message(user_id, ERROR_MESSAGE, kb.delete_message)
