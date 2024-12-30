import random
import phonenumbers
from statistics import mode, median
from datetime import datetime, date, timedelta
from collections import Counter, defaultdict

from octodiary.apis import AsyncMobileAPI
from octodiary.urls import Systems
from octodiary.exceptions import APIError

from app.utils.user.decorators import handle_api_error
from config import ERROR_MESSAGE, ERROR_403_MESSAGE
from app.utils.database import AsyncSessionLocal, db, User, Event, Settings
import app.keyboards.user.keyboards as kb



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


async def user_send_message(user_id, message, markup=None):
    from app import bot
    
    try:
        chat = await bot.get_chat(user_id)
        if markup:
            await bot.send_message(chat_id=chat.id, text=message, reply_markup=markup)
        else:
            await bot.send_message(chat_id=chat.id, text=message)
    except Exception as e:
        return


async def get_emoji_subject(name):
    return EMOJI_SUBJECTS.get(name, random.choice(EMOJI_OTHER_SUBJECTS))


async def get_mark_with_weight(mark, weight):
    return f"{mark}{str(weight).translate(SUBSCRIPT_MAP)}"
    

@handle_api_error()
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
        
        
@handle_api_error()
async def get_marks(user_id, date_object):
    api, user = await get_student(user_id)
    marks = await api.get_marks(
        student_id=user.student_id,
        profile_id=user.profile_id,
        from_date=date_object,
        to_date=date_object,
    )
    
    text = f'🎓 <b>Оценки за</b> {date_object.strftime("%d %B (%a)")}:\n\n'
    
    
    for mark in marks.payload:
        mark_comment = f"\n<blockquote>{mark.comment}</blockquote>" if mark.comment_exists else ""
        text += f'{await get_emoji_subject(mark.subject_name)} <b>{mark.subject_name}:</b>\n    <i><code>{await get_mark_with_weight(mark.value, mark.weight)} - {mark.control_form_name}</code></i>{mark_comment}\n\n'
    
    if len(marks.payload) == 0:
        text = f'❌ <b>У вас нет оценок </b>{date_object.strftime("%d %B (%a)")}'

    return text



@handle_api_error()
async def get_homework(user_id, date_object):
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

    return text


@handle_api_error()
# async def get_homework_by_subject(user_id, subject_id, date_object):
    # api, user = await get_student(user_id)

    # lesson_info = await api.get_lesson_schedule_item(
    #     profile_id=user.profile_id,
    #     student_id=user.student_id,
    #     lesson_id=int(subject_id),
    # )

    # text = f"{await get_emoji_subject(lesson_info.subject_name)} <b>{lesson_info.subject_name}</b> {lesson_info.date.strftime('%d %b')}\n\n"

    # text += f"    <b>Домашние задание:</b>\n"

    # materials = []

    # for homework in lesson_info.lesson_homeworks:
    #     text += f"        - {homework.homework}\n"
    #     materials.append(*[[[url.url for url in item.urls if url.url_type == 'launch'] for item in material.items] for material in homework.materials])

    # text += f"\n    <b>Для выполнения:<b>"
    # for material in materials:
    #     text += f"    - {material}"
        
        
#     return text



async def get_notifications(user_id, all=False, is_checker=False):
    try:
        api, user = await get_student(user_id)

        notifications = await api.get_notifications(
            student_id=user.student_id,
            profile_id=user.profile_id
        )
        
        if len(notifications) <= 0:
            if is_checker:
                return None
            else:
                return "❌ <b>У вас нет уведомлений</b>"
        
        
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                db.select(Settings).filter(Settings.user_id == user_id)
            )
            settings = result.scalar_one_or_none()
    
            result = await session.execute(db.select(Event).filter(Event.student_id == notifications[0].student_profile_id))

            events = result.scalars().all()

            if not events:
                return None
            
            notifications_db = {
                (notif.teacher_id, notif.event_type, notif.date) for notif in events
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
            
        return text

    except APIError as e:
        if not is_checker:
            if e.status_code in [401, 403]:
                await user_send_message(user_id, ERROR_403_MESSAGE, kb.reauth)
            else:
                await user_send_message(user_id, ERROR_MESSAGE, kb.delete_message)
    except Exception as e:
        print(e)
        if not is_checker:
            await user_send_message(user_id, ERROR_MESSAGE, kb.delete_message)


@handle_api_error()
async def get_schedule(user_id, date_object, short=True):
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
        
    return text



@handle_api_error()
async def get_visits(user_id, date_object):
    api, user = await get_student(user_id)
    
    date_start_week = date_object - timedelta(days=date_object.weekday())
    date_week_end = date_start_week + timedelta(days=6)
    
    visits = await api.get_visits(
        profile_id=user.profile_id,
        student_id=user.student_id,
        contract_id=user.contract_id,
        from_date=date_start_week,
        to_date=date_week_end,
    )
    
    text = f'📊 <b>Посещения за неделю ({date_start_week.strftime("%d.%m")}-{date_week_end.strftime("%d.%m")}):</b>\n\n'
    
    for visit in reversed(visits.payload):
        text += f'📅 <b>{visit.date.strftime("%d %B (%a)")}:</b>\n'
        for visit_in_day in visit.visits:
            text += f"    🔒 {visit_in_day.in_}\n    ⏱️ {visit_in_day.duration}\n    🔓 {visit_in_day.out}\n\n"    
        
    return text


@handle_api_error()
async def get_profile(user_id):
    api, user = await get_student(user_id)
    
    data = await api.get_person_data(
        person_id=user.person_id,
        profile_id=user.profile_id
    )
    
    profile = await api.get_family_profile(profile_id=user.profile_id)
    
    balance = await api.get_status(
        profile_id=user.profile_id,
        contract_ids=user.contract_id
    )
    balance = balance.students[0].balance / 100
    
    phone = phonenumbers.parse(f"+7{profile.profile.phone}")

    current_date = datetime.today()
    age = current_date.year - data.birthdate.year
    if (current_date.month, current_date.day) < (data.birthdate.month, data.birthdate.day):
        age -= 1
        
    for children in profile.children:
        if children.last_name == data.lastname and children.first_name == data.firstname and children.middle_name == data.patronymic:
            school = children.school
            class_name = children.class_name

    text = "👤 <b>Профиль</b>\n\n"
    text += f"🆔 <b>ID:</b> <code>{data.id}</code>\n"
    text += f"📝 <b>Имя:</b> <code>{data.firstname}</code>\n"
    text += f"📜 <b>Фамилия:</b> <code>{data.lastname}</code>\n"
    text += f"🧬 <b>Отчество:</b> <code>{data.patronymic}</code>\n\n"

    text += f"✉️ <b>Почта:</b> <code>{profile.profile.email}</code>\n"
    text += f"📱 <b>Телефон:</b> <code>{phonenumbers.format_number(phone, phonenumbers.PhoneNumberFormat.INTERNATIONAL)}</code>\n"
    text += f"🪪 <b>СНИЛС:</b> <code>{data.snils[:3]}-{data.snils[3:6]}-{data.snils[6:9]}-{data.snils[9:]}</code>\n\n"
    
    text += f"💰 <b>Баланс:</b> <code>{balance} ₽</code>\n\n"
    
    text += f"🎂 <b>Дата рождения:</b> <code>{data.birthdate.strftime('%d %B %Y')}</code>\n"
    text += f"🔢 <b>Возраст:</b> <code>{age}</code>\n\n"
    
    text += f"🏫 <b>Школа:</b> <code>{school.short_name}</code>\n"
    text += f"🧑‍💼 <b>Директор:</b> <code>{school.principal}</code>\n"
    text += f"📚 <b>Класс:</b> <code>{class_name}</code>\n\n"
        
    return text


async def time_to_minutes(duration):
    if 'ч.' in duration:
        hours, minutes = map(int, duration.split(" ч."))
        minutes += hours * 60
    else:
        minutes = int(duration) * 60
    return minutes


async def str_to_time(time_str):
    return datetime.strptime(time_str, "%H:%M")


async def minutes_to_time(duration_minutes):
    hours = duration_minutes // 60
    minutes = duration_minutes % 60
    return f"{hours} ч. {minutes} мин."


@handle_api_error()
async def get_results(user_id, quarter):
    quarter = int(quarter) - 1
    
    api, user = await get_student(user_id)
    
    subjects = await api.get_subjects(
        student_id=user.student_id,
        profile_id=user.profile_id
    )
    
    global_marks = []
    max_marks_subject_name = ''
    max_marks_subject_amount = 0
    marks_by_grade = Counter()
    subject_data = []  # Список для хранения данных по каждому предмету

    for subject in subjects.payload:
        subject_marks_info = await api.get_subject_marks_for_subject(
            student_id=user.student_id,
            profile_id=user.profile_id,
            subject_name=subject.subject_name
        )
        
        subject_info = {
            'subject_name': f"{subject.subject_name}",
            'total_marks': 0,
            'frequent_grade': 'Н/Д',
            'marks_count': {}
        }
        
        if len(subject_marks_info.periods) >= 2:
            marks = [int(mark.value) for mark in subject_marks_info.periods[quarter].marks]
            subject_info['total_marks'] = len(marks)
            subject_info['frequent_grade'] = mode(marks)
            
            # Подсчет количества каждой оценки по предмету
            subject_info['marks_count'] = dict(Counter(marks))
            marks_by_grade.update(marks)
            
            subject_info['mark'] = subject_marks_info.periods[quarter].value
            
            for mark in marks:
                global_marks.append(mark)

            # Обновление самого результативного предмета
            if len(marks) > max_marks_subject_amount:
                max_marks_subject_name = subject.subject_name
                max_marks_subject_amount = len(marks)

            subject_data.append(subject_info)

    # Получение информации о четверти
    periods_schedules = await api.get_periods_schedules(
        student_id=user.student_id,
        profile_id=user.profile_id,
        from_date=datetime(date.today().year, 9, 1),
        to_date=datetime(date.today().year + 1, 6, 1),
    )
    
    quarters = []  
    current_start = None  

    # Сортируем расписание
    sorted_schedules = sorted(periods_schedules, key=lambda x: x.date)

    for item in sorted_schedules:
        if item.type == 'vacation' or (item.type == 'holiday' and 'каник' in item.title):
            if current_start:
                quarters.append((current_start, item.date - timedelta(days=1)))
                current_start = None
        elif item.type in ('workday', 'other'):
            if current_start is None:
                current_start = item.date

    if current_start:
        quarters.append((current_start, sorted_schedules[-1].date))
    
    homeworks_short = await api.get_homeworks_short(
        student_id=user.student_id,
        profile_id=user.profile_id,
        from_date=quarters[quarter][0],
        to_date=date.today(),
    )

    dates = [item.date for item in homeworks_short.payload]
    date_counts = Counter(dates)

    # Находим день с наибольшим количеством заданий
    most_homework_date, most_homework_count = max(date_counts.items(), key=lambda x: x[1])
    least_homework_date, least_homework_count = min(date_counts.items(), key=lambda x: x[1])
    
    avg_homework_count = int(median(list(date_counts.values())))


    # Получаем информацию о посещениях
    visits = await api.get_visits(
        profile_id=user.profile_id,
        student_id=user.student_id,
        contract_id=user.contract_id,
        from_date=quarters[quarter][0],
        to_date=quarters[quarter][1],
    )

    # Хранение данных о суммарных длительностях за день
    daily_durations = defaultdict(int)
    longest_day = None
    shortest_day = None
    earliest_in = None
    latest_out = None

    # Обрабатываем посещения
    for entry in visits.payload:
        date_ = entry.date
        for visit in entry.visits:
            # Игнорируем некорректные длительности
            if '-' in visit.duration:
                continue
            # Длительность текущего визита
            duration_minutes = await time_to_minutes(visit.duration.replace(" мин.", ""))
            daily_durations[date_] += duration_minutes

            # Время прихода и ухода
            in_time = await str_to_time(visit.in_)
            out_time = await str_to_time(visit.out)
            
            # Обновляем данные о приходах и уходах
            if not earliest_in or in_time < earliest_in["time"]:
                earliest_in = {"date": date_, "time": in_time}
            if not latest_out or out_time > latest_out["time"]:
                latest_out = {"date": date_, "time": out_time}

    # Поиск самого долгого и короткого дня
    longest_day = max(daily_durations.items(), key=lambda x: x[1])
    shortest_day = min(daily_durations.items(), key=lambda x: x[1])
    
    # Формирование словаря с итоговыми данными
    result = {
        'subjects': subject_data,
        'most_homework_date': most_homework_date,
        'most_homework_count': most_homework_count,
        'least_homework_date': least_homework_date,
        'least_homework_count': least_homework_count,
        'avg_homework_count': avg_homework_count,
        'total_grades': len(global_marks),
        'frequent_grade_overall': mode(global_marks),
        'most_resultive_subject': {
            'name': f"{max_marks_subject_name}",
            'marks_count': max_marks_subject_amount
        },
        'grades_count': dict(marks_by_grade),
        'longest_day': {
            'date': longest_day[0],
            'duration': longest_day[1]
        },
        'shortest_day': {
            'date': shortest_day[0],
            'duration': shortest_day[1]
        },
        'earliest_in': {
            'date': earliest_in["date"],
            'time': earliest_in["time"].strftime("%H:%M")
        },
        'latest_out': {
            'date': latest_out["date"],
            'time': latest_out["time"].strftime("%H:%M")
        }
    }

    return result
    

async def results_format(data, state, subject=None, quarter=None):
    marks_emoji = {
        5: "5️⃣",
        4: "4️⃣",
        3: "3️⃣",
        2: "2️⃣"
    }
    
    if state == 'subjects':
        subject_name = data['subjects'][subject]['subject_name']
        
        text = f"{await get_emoji_subject(subject_name)} <b>{subject_name}</b> ({quarter} четверть)\n"
        text += f'    🎓 <i>Всего оценок:</i> <span class="tg-spoiler">{data["subjects"][subject]["total_marks"]}</span>\n'
        text += f'    🏅 <i>Самая частая оценка:</i> <span class="tg-spoiler">{data["subjects"][subject]["frequent_grade"]}</span>\n'
        text += f'    📈 <i>Балл:</i> <span class="tg-spoiler">{data["subjects"][subject]["mark"]}</span>\n\n'
        text += f'    📔 <b>Оценки:</b>\n'
        for grade, count in sorted(data["subjects"][subject]['marks_count'].items(), reverse=True):
            sticker = marks_emoji.get(grade, "📊")
            text += f'         {sticker}: <span class="tg-spoiler">{count}</span>\n'
        
    elif state == 'overall_results':
        text = f"<b>Общие результаты</b> ({quarter} четверть)\n"
        text += f'    📝 <i>Общее количество оценок:</i> <span class="tg-spoiler">{data["total_grades"]}</span>\n'
        text += f'    🏅 <i>Самая частая оценка:</i> <span class="tg-spoiler">{data["frequent_grade_overall"]}</span>\n'
        text += f'    🌟 <i>Больше всего оценок:</i> <span class="tg-spoiler">{await get_emoji_subject(data["most_resultive_subject"]["name"])} {data["most_resultive_subject"]["name"]} - {data["most_resultive_subject"]["marks_count"]}</span>\n\n'

        text += '    📔 <b>Оценки:</b>\n'
        for grade, count in sorted(data['grades_count'].items(), reverse=True):
            sticker = marks_emoji.get(grade, "📊")
            text += f'         {sticker}: <span class="tg-spoiler">{count}</span>\n'

        text += f'\n    📈 <i>Больше всего домашнего задания:</i> <span class="tg-spoiler">{data["most_homework_date"].strftime("%d %B")} ({data["most_homework_count"]})</span>\n'
        text += f'    📉 <i>Меньше всего домашнего задания:</i> <span class="tg-spoiler">{data["least_homework_date"].strftime("%d %B")} ({data["least_homework_count"]})</span>\n'
        text += f'    📊 <i>Среднее количество домашнего задания:</i> <span class="tg-spoiler">{data["avg_homework_count"]}</span>\n\n'
        
        text += f'    🕒 <i>Самый долгий день:</i> <span class="tg-spoiler">{data["longest_day"]["date"].strftime("%d %B")} - {await minutes_to_time(data["longest_day"]["duration"])}</span>\n'
        text += f'    📅 <i>Самый короткий день:</i> <span class="tg-spoiler">{data["shortest_day"]["date"].strftime("%d %B")} - {await minutes_to_time(data["shortest_day"]["duration"])}</span>\n'
        text += f'    ⏰ <i>Самый ранний заход:</i> <span class="tg-spoiler">{data["earliest_in"]["date"].strftime("%d %B")} - {data["earliest_in"]["time"]}</span>\n'
        text += f'    ⏳ <i>Самый поздний уход:</i> <span class="tg-spoiler">{data["latest_out"]["date"].strftime("%d %B")} - {data["latest_out"]["time"]}</span>\n'

        
    return text 



@handle_api_error()
async def get_rating_rank_class(user_id):
    api, student = await get_student(user_id)
    profile = await api.get_family_profile(profile_id=student.profile_id)
    
    rating = await api.get_rating_rank_class(
        profile_id=student.profile_id,
        person_id=student.person_id,
        class_unit_id=profile.children[0].class_unit_id,
    )
    
    text = ""
    
    grouped = defaultdict(list)
    for user in rating:
        grouped[user.rank.average_mark_five].append(user)
        
    place_in_class = 0
    
    for avg_mark, users in sorted(grouped.items(), reverse=True):
        count = len(users)
        filled = int((avg_mark / 5) * 20)
        bar = f'{"▇" * filled}{"▁" * (20 - filled)}'

        # Форматирование с фиксированными длинами
        place = str(users[0].rank.rank_place).rjust(2)
        avg_mark_str = f'{avg_mark:.2f}'.rjust(5)
        count_str = str(count)
        
        if users[0].person_id == student.person_id:
            place_in_class = users[0].rank.rank_place
            text += f'{place} {bar} {avg_mark_str} ({count_str} чел.) 🌟\n'
        else:
            text += f'{place} {bar} {avg_mark_str} ({count_str} чел.)\n'
            
    return f"📈 Рейтинг по классу (Ваше место: {place_in_class})\n<pre>{text}</pre>"