from collections import Counter, defaultdict
from datetime import date, datetime, time, timedelta
import json
from statistics import median, mode

from octodiary.exceptions import APIError

from app.utils.database import AsyncSessionLocal, db, Settings
from app.utils.user.decorators import handle_api_error
from app.utils.user.cache import get_ttl, redis_client
from app.utils.user.utils import get_emoji_subject, get_student


async def time_to_minutes(duration):
    if "ч." in duration:
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


async def convert_dates(obj):
        if isinstance(obj, (date, datetime)):
            return obj.isoformat()
        elif isinstance(obj, dict):
            return {k: convert_dates(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [convert_dates(item) for item in obj]
        else:
            return obj
        
        
async def parse_date(date_str):
        if date_str == "Н/Д":
            return "Н/Д"
        try:
            return datetime.fromisoformat(date_str).date()
        except:
            return date_str


@handle_api_error()
async def get_results(user_id, quarter):
    quarter = int(quarter)
    target_title = f"{quarter} четверть"
    quarter -= 1
    
    async with AsyncSessionLocal() as session:
        result = await session.execute(db.select(Settings).filter_by(user_id=user_id))
        settings: Settings = result.scalar_one_or_none()

    use_cache = settings and settings.experimental_features and settings.use_cache
    cache_key = f"results:{user_id}:{quarter + 1}"  # quarter+1 потому что мы уменьшили quarter выше

    # Пытаемся получить данные из кэша
    if use_cache:
        cached_data = await redis_client.get(cache_key)
        if cached_data:
            return json.loads(cached_data)


    api, user = await get_student(user_id)

    subjects = await api.get_subjects(
        student_id=user.student_id, profile_id=user.profile_id
    )

    global_marks = []
    max_marks_subject_name = ""
    max_marks_subject_amount = 0
    marks_by_grade = Counter()
    subject_data = []  # Список для хранения данных по каждому предмету

    for subject in subjects.payload:
        subject_marks_info = await api.get_subject_marks_for_subject(
            student_id=user.student_id,
            profile_id=user.profile_id,
            subject_name=subject.subject_name,
        )

        subject_info = {
            "subject_name": f"{subject.subject_name}",
            "total_marks": 0,
            "frequent_grade": "Н/Д",
            "marks_count": {},
        }

        # if len(subject_marks_info.periods) >= 2:
        target_period = next(
            (p for p in subject_marks_info.periods if p.title == target_title), None
        )

        if target_period is not None:
            # print(f"{subject.subject_name}: {len(subject_marks_info.periods)}")
            # marks = [
            #     int(mark.value) for mark in subject_marks_info.periods[quarter].marks
            # ]
            marks = [int(mark.value) for mark in target_period.marks]
            subject_info["total_marks"] = len(marks)
            subject_info["frequent_grade"] = mode(marks)

            # Подсчет количества каждой оценки по предмету
            subject_info["marks_count"] = dict(Counter(marks))
            marks_by_grade.update(marks)

            # subject_info["mark"] = subject_marks_info.periods[quarter].value
            subject_info["mark"] = target_period.value

            for mark in marks:
                global_marks.append(mark)

            # Обновление самого результативного предмета
            if len(marks) > max_marks_subject_amount:
                max_marks_subject_name = subject.subject_name
                max_marks_subject_amount = len(marks)

            subject_data.append(subject_info)

    today = date.today()
    start_year = today.year if today >= date(today.year, 9, 1) else today.year - 1

    # Получение информации о четверти
    periods_schedules = await api.get_periods_schedules(
        student_id=user.student_id,
        profile_id=user.profile_id,
        from_date=datetime(start_year, 9, 1),
        to_date=datetime(start_year + 1, 6, 1),
    )

    quarters = []
    current_start = None

    # Сортируем расписание
    sorted_schedules = sorted(periods_schedules, key=lambda x: x.date)

    for item in sorted_schedules:
        if item.type == "vacation" or (
            item.type == "holiday" and 
            item.title and 
            "каник" in item.title
        ):
            if current_start:
                quarters.append((current_start, item.date - timedelta(days=1)))
                current_start = None
        elif item.type in ("workday", "other"):
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
    most_homework_date, most_homework_count = max(
        date_counts.items(), key=lambda x: x[1]
    )
    least_homework_date, least_homework_count = min(
        date_counts.items(), key=lambda x: x[1]
    )

    avg_homework_count = int(median(list(date_counts.values())))

    try:
        # Получаем информацию о посещениях
        visits = await api.get_visits(
            profile_id=user.profile_id,
            student_id=user.student_id,
            contract_id=user.contract_id,
            from_date=quarters[quarter][0],
            to_date=quarters[quarter][1],
        )
    except APIError as e:
        visits = None

    # Хранение данных о суммарных длительностях за день
    daily_durations = defaultdict(int)
    longest_day = None
    shortest_day = None
    earliest_in = None
    latest_out = None

    # Обрабатываем посещения
    if visits is not None:
        for entry in visits.payload:
            date_ = entry.date
            for visit in entry.visits:
                # Игнорируем некорректные длительности
                if "-" in visit.duration:
                    continue
                # Длительность текущего визита
                duration_minutes = await time_to_minutes(
                    visit.duration.replace(" мин.", "")
                )
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
    else:
        longest_day = ("Н/Д", 0)
        shortest_day = ("Н/Д", 0)
        earliest_in = {"date": "Н/Д", "time": time(0, 0)}
        latest_out = {"date": "Н/Д", "time": time(0, 0)}

    # Формирование словаря с итоговыми данными
    result = {
        "subjects": subject_data,
        "most_homework_date": await convert_dates(most_homework_date),
        "most_homework_count": most_homework_count,
        "least_homework_date": await convert_dates(least_homework_date),
        "least_homework_count": least_homework_count,
        "avg_homework_count": avg_homework_count,
        "total_grades": len(global_marks),
        "frequent_grade_overall": mode(global_marks),
        "most_resolutive_subject": {
            "name": f"{max_marks_subject_name}",
            "marks_count": max_marks_subject_amount,
        },
        "grades_count": dict(marks_by_grade),
        "longest_day": {"date": await convert_dates(longest_day[0]), "duration": longest_day[1]},
        "shortest_day": {"date": await convert_dates(shortest_day[0]), "duration": shortest_day[1]},
        "earliest_in": {
            "date": await convert_dates(earliest_in["date"]),
            "time": earliest_in["time"].strftime("%H:%M"),
        },
        "latest_out": {
            "date": await convert_dates(latest_out["date"]),
            "time": latest_out["time"].strftime("%H:%M"),
        },
    }
    
    if use_cache:
        ttl = await get_ttl()
        await redis_client.setex(cache_key, ttl, json.dumps(result))

    return result


async def results_format(data, state, subject=None, quarter=None):
    marks_emoji = {5: "5️⃣", 4: "4️⃣", 3: "3️⃣", 2: "2️⃣"}

    if state == "subjects":
        subject_name = data["subjects"][subject]["subject_name"]

        text = f"{await get_emoji_subject(subject_name)} <b>{subject_name}</b> ({quarter} четверть)\n"
        text += f'    🎓 <i>Всего оценок:</i> <span class="tg-spoiler">{data["subjects"][subject]["total_marks"]}</span>\n'
        text += f'    🏅 <i>Самая частая оценка:</i> <span class="tg-spoiler">{data["subjects"][subject]["frequent_grade"]}</span>\n'
        text += f'    📈 <i>Балл:</i> <span class="tg-spoiler">{data["subjects"][subject]["mark"]}</span>\n\n'
        text += f"    📔 <b>Оценки:</b>\n"
        for grade, count in sorted(
            data["subjects"][subject]["marks_count"].items(), reverse=True
        ):
            sticker = marks_emoji.get(int(grade), "📊")
            text += f'         {sticker}: <span class="tg-spoiler">{count}</span>\n'

    elif state == "overall_results":
        text = f"<b>Общие результаты</b> ({quarter} четверть)\n"
        text += f'    📝 <i>Общее количество оценок:</i> <span class="tg-spoiler">{data["total_grades"]}</span>\n'
        text += f'    🏅 <i>Самая частая оценка:</i> <span class="tg-spoiler">{data["frequent_grade_overall"]}</span>\n'
        text += f'    🌟 <i>Больше всего оценок:</i> <span class="tg-spoiler">{await get_emoji_subject(data["most_resolutive_subject"]["name"])} {data["most_resolutive_subject"]["name"]} - {data["most_resolutive_subject"]["marks_count"]}</span>\n\n'

        text += "    📔 <b>Оценки:</b>\n"
        for grade, count in sorted(data["grades_count"].items(), reverse=True):
            sticker = marks_emoji.get(int(grade), "📊")
            text += f'         {sticker}: <span class="tg-spoiler">{count}</span>\n'

        most_hw_date = await parse_date(data["most_homework_date"])
        least_hw_date = await parse_date(data["least_homework_date"])
        
        text += f'\n    📈 <i>Больше всего домашнего задания:</i> <span class="tg-spoiler">{most_hw_date.strftime("%d %B") if most_hw_date != "Н/Д" else "Н/Д"} ({data["most_homework_count"]})</span>\n'
        text += f'    📉 <i>Меньше всего домашнего задания:</i> <span class="tg-spoiler">{least_hw_date.strftime("%d %B") if least_hw_date != "Н/Д" else "Н/Д"} ({data["least_homework_count"]})</span>\n'
        text += f'    📊 <i>Среднее количество домашнего задания:</i> <span class="tg-spoiler">{data["avg_homework_count"]}</span>\n\n'

        # Аналогично для остальных дат
        longest_date = await parse_date(data["longest_day"]["date"])
        shortest_date = await parse_date(data["shortest_day"]["date"])
        earliest_date = await parse_date(data["earliest_in"]["date"])
        latest_date = await parse_date(data["latest_out"]["date"])

        text += f'    🕒 <i>Самый долгий день:</i> <span class="tg-spoiler">{longest_date.strftime("%d %B") if longest_date != "Н/Д" else "Н/Д"} - {await minutes_to_time(data["longest_day"]["duration"])}</span>\n'
        text += f'    📅 <i>Самый короткий день:</i> <span class="tg-spoiler">{shortest_date.strftime("%d %B") if shortest_date != "Н/Д" else "Н/Д"} - {await minutes_to_time(data["shortest_day"]["duration"])}</span>\n'
        text += f'    ⏰ <i>Самый ранний заход:</i> <span class="tg-spoiler">{earliest_date.strftime("%d %B") if earliest_date != "Н/Д" else "Н/Д"} - {data["earliest_in"]["time"]}</span>\n'
        text += f'    ⏳ <i>Самый поздний уход:</i> <span class="tg-spoiler">{latest_date.strftime("%d %B") if latest_date != "Н/Д" else "Н/Д"} - {data["latest_out"]["time"]}</span>\n'

    return text
