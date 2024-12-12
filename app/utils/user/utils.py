import random
from datetime import datetime, timedelta

from octodiary.apis import AsyncMobileAPI
from octodiary.urls import Systems

from config import ERROR_MESSAGE
from app.utils.database import AsyncSessionLocal, db, User, Event, Settings



EMOJI_SUBJECTS = {
    "Иностранный (английский) язык": "🇬🇧",
    "Алгебра": "➗",
    "Вероятность и статистика": "📊",
    "Геометрия": "📐",
    "Информатика": "💻",
    "Математика": "🧮",
    "Литература": "📚",
    "Русский язык": "🇷🇺",
    "Практикум по русскому языку": "📝",
    "Основы безопасности и защиты Родины": "🛡️",
    "Биология": "🧬",
    "Физика": "🔬",
    "Химия": "⚗️",
    "Физическая культура": "🏋️",
    "География": "🗺️",
    "История": "🏺",
    "Обществознание": "⚖️",
    "Труд (технология)": "🔧",
}

EMOJI_OTHER_SUBJECTS = ["📒", "📕", "📗", "📘", "📙"]

EMOJI_NUMBERS = {
    1: "1️⃣",
    2: "2️⃣",
    3: "3️⃣",
    4: "4️⃣",
    5: "5️⃣",
    6: "6️⃣",
    7: "7️⃣",
    8: "8️⃣",
    9: "9️⃣",
    10: "🔟",
}

SUBSCRIPT_MAP = str.maketrans("12345", "₁₂₃₄₅")



async def get_emoji_subject(name):
    return EMOJI_SUBJECTS.get(name, random.choice(EMOJI_OTHER_SUBJECTS))


async def get_mark_with_weight(mark, weight):
    return f"{mark}{str(weight).translate(SUBSCRIPT_MAP)}"
    

async def get_student(user_id):
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            db.select(User).filter_by(user_id=user_id)
        )
        user = result.scalar_one_or_none()

        if user:
            api = AsyncMobileAPI(system=Systems.MES)
            api.token = user.token
            return api, user
        else:
            return None, None
        
        
async def get_marks(user_id, date_object):
    try:
        api, user = await get_student(user_id)
        marks = await api.get_marks(
            student_id=user.student_id,
            profile_id=user.profile_id,
            from_date=date_object,
            to_date=date_object,
        )
        
        text = f'🎓 <b>Оценки за</b> {date_object.strftime("%d %B (%a)")}:\n\n'
        
        
        for mark in marks.payload:
            text += f'{await get_emoji_subject(mark.subject_name)} <b>{mark.subject_name}:</b>\n    <i><code>{await get_mark_with_weight(mark.value, mark.weight)} - {mark.control_form_name}</code></i>\n\n'
        
        if len(marks.payload) == 0:
            text = f'❌ <b>У вас нет оценок </b>{date_object.strftime("%d %B (%a)")}'
    except Exception as e:
        text = ERROR_MESSAGE

    return text



async def get_homework(user_id, date_object):
    try:
        api, user = await get_student(user_id)

        homework = await api.get_homeworks_short(
            student_id=user.student_id,
            profile_id=user.profile_id,
            from_date=date_object,
            to_date=date_object,
        )
        
        text = f'📚 <b>Домашние задания на</b> {date_object.strftime("%d %B (%a)")}:\n\n'
        
        for task in homework.payload:
            description = task.description.rstrip("\n")
            text += f'{await get_emoji_subject(task.subject_name)} <b>{task.subject_name}:</b>\n    <code>{description}</code>\n\n'
        
        if len(homework.payload) == 0:
            text = f'❌ <b>У вас нет домашних заданий на </b>{date_object.strftime("%d %B (%a)")}'
    except Exception as e:
        text = ERROR_MESSAGE

    return text



async def get_notifications(user_id, all=False, is_checker=False):
    try:
        api, user = await get_student(user_id)
        
        notifications = await api.get_notifications(
            student_id=user.student_id,
            profile_id=user.profile_id
        )
        
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                db.select(Settings).filter(Settings.user_id == user_id)
            )
            settings = result.scalar_one_or_none()
            
            result = await session.execute(db.select(Event).filter(Event.student_id == notifications[0].student_profile_id))
            notifications_db = {
                (notif.teacher_id, notif.event_type, notif.date) for notif in result.scalars().all()
            }
            
            new_notifications = []
            
            for notification in notifications:
                notification_id = (notification.author_profile_id, notification.event_type, notification.created_at)
                
                if notification_id not in notifications_db:
                    new_notifications.append(notification)
                    
                    new_event = Event(
                        student_id=notification.student_profile_id,
                        event_type=notification.event_type,
                        subject_name=notification.subject_name,
                        date=notification.created_at,
                        teacher_id=notification.author_profile_id
                    )
                    session.add(new_event)
            
            await session.commit()
        
        if not all:
            notifications = new_notifications
        
        # Фильтруем уведомления на основе настроек
        filtered_notifications = []
        for notification in notifications:
            if notification.event_type == 'create_mark' and (not is_checker or settings.enable_new_mark_notification):
                filtered_notifications.append(notification)
            elif notification.event_type == 'update_mark' and (not is_checker or settings.enable_new_mark_notification):
                filtered_notifications.append(notification)
            elif notification.event_type == 'delete_mark' and (not is_checker or settings.enable_new_mark_notification):
                filtered_notifications.append(notification)
            elif notification.event_type == 'create_homework' and (not is_checker or settings.enable_homework_notification):
                filtered_notifications.append(notification)
            elif notification.event_type == 'update_homework' and (not is_checker or settings.enable_homework_notification):
                filtered_notifications.append(notification)
        
        # Проверяем, есть ли отфильтрованные уведомления
        if len(filtered_notifications) <= 0:
            if is_checker:
                return None
            return "❌ <b>У вас нет новых уведомлений</b>"
        
        # Формируем текст только для отфильтрованных уведомлений
        text = f"🔔 <b>Уведомления ({len(filtered_notifications)}):</b>\n\n"
        
        for notification in filtered_notifications:
            subject_name = f'{await get_emoji_subject(notification.subject_name)} {notification.subject_name} ({notification.created_at.strftime("%d.%m %H:%M:%S")})\n        '
                
            if notification.event_type == 'create_mark':
                text += subject_name
                text += f'<b>Новая оценка:</b>\n            <i><code>{await get_mark_with_weight(notification.new_mark_value, notification.new_mark_weight)} - {notification.control_form_name}</code></i>\n\n'
                
            elif notification.event_type == 'update_mark':
                text += subject_name
                text += f'<b>Изменение оценки:</b>\n            <i><code>{notification.old_mark_value} -> {get_mark_with_weight(notification.new_mark_value, notification.new_mark_weight)} - {notification.control_form_name}</code></i>\n\n'
                
            elif notification.event_type == 'delete_mark':
                text += subject_name
                text += f'<b>Удаление оценки:</b>\n            <i><code>{notification.old_mark_value} - {notification.control_form_name}</code></i>\n\n'
                
            elif notification.event_type == 'create_homework':
                text += subject_name
                description = notification.new_hw_description.rstrip("\n")
                text += f'<b>Новое домашние задание:</b>\n            <i><code>{description}</code></i>\n\n'
                
            elif notification.event_type == 'update_homework':
                text += subject_name
                description = notification.new_hw_description.rstrip("\n")
                text += f'<b>Изменение домашних задания:</b>\n            <i><code>{description}</code></i>\n\n'
                
    except Exception as e:
        if is_checker:
            text = None
        else:
            text = ERROR_MESSAGE
        
    return text


async def get_schedule(user_id, date_object, short=True):
    try:
        api, user = await get_student(user_id)
        
        schedule = await api.get_events(
            person_id=user.person_id,
            mes_role=user.role,
            begin_date=date_object,
            end_date=date_object
        )
        
        text = f'📅 <b>Расписание на</b> {date_object.strftime("%d %B (%a)")}:\n\n'
        
        for num, event in enumerate(schedule.response, 1):
            start_time = event.start_at.strftime("%H:%M")
            end_time = event.finish_at.strftime("%H:%M")
            
            if not short:
                lesson_info = await api.get_lesson_schedule_item(
                    profile_id=user.profile_id,
                    lesson_id=event.id,
                    student_id=user.student_id,
                    type=event.source
                )
                
                text += f'{EMOJI_NUMBERS.get(num, f"{num}️")} {await get_emoji_subject(event.subject_name)} <b>{event.subject_name}</b> <i>({start_time}-{end_time})</i>\n    📍 {event.room_number}\n    👤<i>{lesson_info.teacher.first_name[0]}. {lesson_info.teacher.middle_name[0]}. {lesson_info.teacher.last_name}</i> {" - 🔄 замена" if event.replaced else ""}\n\n'
            else:
                replased_text = "\n    👤 - 🔄 замена"
                text += f'{EMOJI_NUMBERS.get(num, f"{num}️")} {await get_emoji_subject(event.subject_name)} <b>{event.subject_name}</b> <i>({start_time}-{end_time})</i>\n    📍 {event.room_number}{replased_text if event.replaced else ""}\n\n'
        
    except Exception as e:
        text = ERROR_MESSAGE
        
    return text