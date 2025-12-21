import json
from collections import Counter, defaultdict
from datetime import date, datetime, time, timedelta
from statistics import median, mode

from octodiary.exceptions import APIError

from app.utils.database import AsyncSessionLocal, Settings, db
from app.utils.user.cache import get_ttl, redis_client
from app.utils.user.decorators import handle_api_error
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


async def get_quarter_periods(periods_schedules):
    quarters = []
    current_start = None

    sorted_schedules = sorted(periods_schedules, key=lambda x: x.date)

    for item in sorted_schedules:
        if item.type == "vacation" or (
            item.title and 
            "каник" in item.title.lower()
        ):
            if current_start:
                quarters.append((current_start, item.date - timedelta(days=1)))
                current_start = None
        elif item.type in ("workday", "other"):
            if current_start is None:
                current_start = item.date

    if current_start:
        quarters.append((current_start, sorted_schedules[-1].date))

    return quarters


async def get_half_year_periods(periods_schedules):
    quarters = await get_quarter_periods(periods_schedules)
    
    half_years = []
    
    if len(quarters) >= 2:
        half_years.append((quarters[0][0], quarters[1][1]))
    
    if len(quarters) >= 4:
        half_years.append((quarters[2][0], quarters[3][1]))
    elif len(quarters) == 3:
        half_years.append((quarters[2][0], quarters[2][1]))
    
    return half_years


async def get_trimester_periods(periods_schedules):
    quarters = await get_quarter_periods(periods_schedules)
    
    trimesters = []
    
    if len(quarters) >= 3:
        trimesters.append((quarters[0][0], quarters[1][1]))
        trimesters.append((quarters[2][0], quarters[2][1]))
        if len(quarters) >= 4:
            trimesters.append((quarters[3][0], quarters[3][1]))
    elif len(quarters) == 2:
        trimesters = quarters
    
    return trimesters


async def detect_period_type(api, user):
    """Определяет тип учебных периодов (четверти/полугодия/триместры)"""
    subjects = await api.get_subjects(
        student_id=user.student_id, profile_id=user.profile_id
    )
    
    if not subjects.payload:
        return "quarters"
    
    first_subject = subjects.payload[0]
    subject_marks_info = await api.get_subject_marks_for_subject(
        student_id=user.student_id,
        profile_id=user.profile_id,
        subject_name=first_subject.subject_name,
    )
    
    period_titles = [p.title.lower() for p in subject_marks_info.periods if p.title]
    
    if any("полугодие" in title for title in period_titles):
        return "half_years"
    elif any("триместр" in title for title in period_titles):
        return "trimesters"
    elif any("четверть" in title for title in period_titles):
        return "quarters"
    else:
        if len(subject_marks_info.periods) <= 2:
            return "half_years"
        elif len(subject_marks_info.periods) == 3:
            return "trimesters"
        else:
            return "quarters"


async def get_current_period(api, user, period_type):
    today = date.today()
    start_year = today.year if today >= date(today.year, 9, 1) else today.year - 1
    
    periods_schedules = await api.get_periods_schedules(
        student_id=user.student_id,
        profile_id=user.profile_id,
        from_date=datetime(start_year, 9, 1),
        to_date=datetime(start_year + 1, 6, 1),
    )
    
    if period_type == "quarters":
        periods = await get_quarter_periods(periods_schedules)
    elif period_type == "half_years":
        periods = await get_half_year_periods(periods_schedules)
    elif period_type == "trimesters":
        periods = await get_trimester_periods(periods_schedules)
    else:
        periods = await get_quarter_periods(periods_schedules)
    
    for i, (start_date, end_date) in enumerate(periods, 1):
        if start_date <= today <= end_date:
            return i
    
    for i, (start_date, end_date) in reversed(list(enumerate(periods, 1))):
        if today > end_date:
            return i
    
    return 1


async def get_period_display_name(period_type, period_number):
    period_names = {
        "quarters": {1: "1 четверть", 2: "2 четверть", 3: "3 четверть", 4: "4 четверть"},
        "half_years": {1: "1 полугодие", 2: "2 полугодие"},
        "trimesters": {1: "1 триместр", 2: "2 триместр", 3: "3 триместр"}
    }
    
    return period_names.get(period_type, {}).get(period_number, f"Период {period_number}")


async def get_available_periods(api, user, period_type, current_date=None):
    if current_date is None:
        current_date = date.today()
    
    start_year = current_date.year if current_date >= date(current_date.year, 9, 1) else current_date.year - 1
    
    periods_schedules = await api.get_periods_schedules(
        student_id=user.student_id,
        profile_id=user.profile_id,
        from_date=datetime(start_year, 9, 1),
        to_date=datetime(start_year + 1, 6, 1),
    )
    
    if period_type == "quarters":
        periods_dates = await get_quarter_periods(periods_schedules)
    elif period_type == "half_years":
        periods_dates = await get_half_year_periods(periods_schedules)
    elif period_type == "trimesters":
        periods_dates = await get_trimester_periods(periods_schedules)
    else:
        periods_dates = await get_quarter_periods(periods_schedules)
    
    available_periods = []
    
    for i, (period_start, period_end) in enumerate(periods_dates, 1):
        if current_date >= period_start:
            available_periods.append(i)
    
    return available_periods
    

async def get_school_days_from_schedule(schedule, period_start, period_end, include_future=False):
    """Получает все дни с уроками из расписания"""
    school_days = set()
    if not schedule:
        return school_days
    today = date.today()

    for item in schedule.response:
        if item.source != "PLAN":
            continue
        item_date = item.start_at.date()
        if period_start <= item_date <= period_end:
            if not include_future and item_date > today:
                continue
            
            if (item.cancelled is False and 
                item.lesson_type == 'NORMAL' and 
                not item.is_missed_lesson):
                school_days.add(item_date)
    
    return school_days


@handle_api_error()
async def get_results(user_id, period_number, period_type="quarters", cache_bypass=False):
    period_number = int(period_number)
    
    period_name_templates = {
        "quarters": f"{period_number} четверть",
        "half_years": f"{period_number} полугодие", 
        "trimesters": f"{period_number} триместр"
    }
    
    async with AsyncSessionLocal() as session:
        result = await session.execute(db.select(Settings).filter_by(user_id=user_id))
        settings: Settings = result.scalar_one_or_none()

    use_cache = settings and settings.experimental_features and settings.use_cache
    cache_key = f"results:{user_id}:{period_type}:{period_number}"

    if use_cache and not cache_bypass:
        cached_data = await redis_client.get(cache_key)
        if cached_data:
            return json.loads(cached_data)


    api, user = await get_student(user_id)

    today = date.today()
    start_year = today.year if today >= date(today.year, 9, 1) else today.year - 1

    periods_schedules = await api.get_periods_schedules(
        student_id=user.student_id,
        profile_id=user.profile_id,
        from_date=datetime(start_year, 9, 1),
        to_date=datetime(start_year + 1, 6, 1),
    )

    subjects = await api.get_subjects(
        student_id=user.student_id, profile_id=user.profile_id
    )
    
    detected_period_type = period_type
    uses_half_years = False

    if period_type is None and subjects.payload:
        first_subject = subjects.payload[0]
        subject_marks_info = await api.get_subject_marks_for_subject(
            student_id=user.student_id,
            profile_id=user.profile_id,
            subject_name=first_subject.subject_name,
        )
        
        period_titles_list = [p.title for p in subject_marks_info.periods if p.title]
        
        uses_half_years = any("полугодие" in title.lower() for title in period_titles_list)
        
        if uses_half_years:
            detected_period_type = "half_years"
        else:
            detected_period_type = "quarters"
    
    if detected_period_type in period_name_templates:
        target_title = period_name_templates[detected_period_type]
    else:
        target_title = f"{period_number} период"
    
    if detected_period_type == "half_years":
        periods = await get_half_year_periods(periods_schedules)
        uses_half_years = True
    elif detected_period_type == "trimesters":
        periods = await get_trimester_periods(periods_schedules)
    else:
        periods = await get_quarter_periods(periods_schedules)
        uses_half_years = False

    if period_number > len(periods):
        raise ValueError(f"Запрошен период {period_number}, но доступно только {len(periods)} периодов")

    period_start, period_end = periods[period_number - 1]

    global_marks = []
    max_marks_subject_name = ""
    max_marks_subject_amount = 0
    marks_by_grade = Counter()
    subject_data = []

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
            "mark": "Н/Д",
        }

        target_period = next(
            (p for p in subject_marks_info.periods if p.title == target_title), None
        )

        if target_period is not None:
            marks = [int(mark.value) for mark in target_period.marks if mark.value.isdigit()]
            if marks:
                subject_info["total_marks"] = len(marks)
                subject_info["frequent_grade"] = mode(marks)
                subject_info["marks_count"] = dict(Counter(marks))
                marks_by_grade.update(marks)
                subject_info["mark"] = target_period.value

                global_marks.extend(marks)

                if len(marks) > max_marks_subject_amount:
                    max_marks_subject_name = subject.subject_name
                    max_marks_subject_amount = len(marks)
            
            subject_data.append(subject_info)


    homeworks_short = await api.get_homeworks_short(
        student_id=user.student_id,
        profile_id=user.profile_id,
        from_date=period_start,
        to_date=min(date.today(), period_end),
    )

    dates = [item.date for item in homeworks_short.payload]
    date_counts = Counter(dates)

    if date_counts:
        most_homework_date, most_homework_count = max(
            date_counts.items(), key=lambda x: x[1]
        )
        least_homework_date, least_homework_count = min(
            date_counts.items(), key=lambda x: x[1]
        )
        avg_homework_count = int(median(list(date_counts.values())))
    else:
        most_homework_date = least_homework_date = None
        most_homework_count = least_homework_count = 0
        avg_homework_count = 0

    try:
        visits = await api.get_visits(
            profile_id=user.profile_id,
            student_id=user.student_id,
            contract_id=user.contract_id,
            from_date=period_start,
            to_date=period_end,
        )
        
        schedule = await api.get_events(
            person_id=user.person_id,
            mes_role=user.role,
            begin_date=period_start,
            end_date=period_end,
        )
    except APIError as e:
        visits = None
        schedule = None

    daily_durations = defaultdict(int)
    longest_day = None
    shortest_day = None
    earliest_in = None
    latest_out = None

    total_school_days = 0
    visited_days = 0
    skipped_days = 0
    total_time_in_school = 0
    
    school_days_from_schedule = await get_school_days_from_schedule(schedule, period_start, period_end)
    total_school_days = len(school_days_from_schedule)
    
    lessons_by_day = defaultdict(list)
    total_lessons = 0
    
    if schedule:
        for item in schedule.response:
            if (item.cancelled is False and 
                item.lesson_type == 'NORMAL' and 
                not item.is_missed_lesson and
                period_start <= item.start_at.date() <= period_end):
                
                day = item.start_at.date()
                lessons_by_day[day].append({
                    "subject": item.subject_name,
                    "start": item.start_at.time(),
                    "end": item.finish_at.time(),
                    "room": item.room_name or item.room_number,
                })
                total_lessons += 1

    if visits is not None and visits.payload:
        visited_dates = set()
        
        for entry in visits.payload:
            date_ = entry.date
            
            if date_ not in school_days_from_schedule:
                # Не учебный день - пропускаем
                continue
            
            day_has_valid_visit = False
            
            for visit in entry.visits:
                if "-" in visit.duration:
                    # Пропуск в учебный день
                    continue
                
                # Нормальное посещение в учебный день
                if not day_has_valid_visit:
                    visited_dates.add(date_)
                    visited_days += 1
                    day_has_valid_visit = True
                
                duration_minutes = await time_to_minutes(
                    visit.duration.replace(" мин.", "")
                )
                daily_durations[date_] += duration_minutes
                total_time_in_school += duration_minutes

                in_time = await str_to_time(visit.in_)
                out_time = await str_to_time(visit.out)

                if not earliest_in or in_time < earliest_in["time"]:
                    earliest_in = {"date": date_, "time": in_time}
                if not latest_out or out_time > latest_out["time"]:
                    latest_out = {"date": date_, "time": out_time}
                    
        skipped_days = 0
        for school_day in school_days_from_schedule:
            if school_day not in visited_dates:
                print(school_day)
                skipped_days += 1
    else:
        # Если нет данных о посещениях
        visited_days = 0
        skipped_days = total_school_days
        
    if daily_durations:
        longest_day = max(daily_durations.items(), key=lambda x: x[1])
        shortest_day = min(daily_durations.items(), key=lambda x: x[1])
    else:
        longest_day = None
        shortest_day = None

    if not longest_day:
        longest_day = ("Н/Д", 0)
    if not shortest_day:
        shortest_day = ("Н/Д", 0)
    if not earliest_in:
        earliest_in = {"date": "Н/Д", "time": time(0, 0)}
    if not latest_out:
        latest_out = {"date": "Н/Д", "time": time(0, 0)}

    
    total_hours = total_time_in_school // 60
    total_minutes = total_time_in_school % 60
    avg_time_per_day = total_time_in_school // visited_days if visited_days > 0 else 0
    avg_hours = avg_time_per_day // 60
    avg_minutes = avg_time_per_day % 60
    
    # Процент посещаемости
    attendance_rate = round(visited_days / total_school_days * 100, 1) if total_school_days > 0 else 0
    
    avg_lessons_per_day = total_lessons / total_school_days if total_school_days > 0 else 0
    
    result = {
        "period_type": detected_period_type or "quarters",
        "period_title": target_title,
        "period_number": period_number,
        "subjects": subject_data,
        "most_homework_date": await convert_dates(most_homework_date) if most_homework_date else "Н/Д",
        "most_homework_count": most_homework_count,
        "least_homework_date": await convert_dates(least_homework_date) if least_homework_date else "Н/Д",
        "least_homework_count": least_homework_count,
        "avg_homework_count": avg_homework_count,
        "total_grades": len(global_marks),
        "frequent_grade_overall": str(mode(global_marks)) if global_marks else 'н/д',
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
        # Статистика посещаемости
        "total_school_days": total_school_days,
        "visited_days": visited_days,
        "skipped_days": skipped_days,
        "attendance_rate": attendance_rate,
        # Время в школе
        "total_school_time_minutes": total_time_in_school,
        "total_school_time": f"{total_hours} ч. {total_minutes} мин.",
        "avg_school_time_per_day": f"{avg_hours} ч. {avg_minutes} мин." if visited_days > 0 else "0 мин.",
        # Дополнительная статистика
        "total_lessons": total_lessons,
        "avg_lessons_per_day": round(avg_lessons_per_day, 1),
        # Информация о периоде
        "period_start": period_start.isoformat(),
        "period_end": period_end.isoformat(),
        "period_duration_days": (period_end - period_start).days,
    }
    
    if use_cache:
        ttl = await get_ttl()
        await redis_client.setex(cache_key, ttl, json.dumps(result))

    return result


async def results_format(data, state, subject=None, period_number=None, period_type=None):
    marks_emoji = {5: "5️⃣", 4: "4️⃣", 3: "3️⃣", 2: "2️⃣"}
    
    period_display = await get_period_display_name(period_type, period_number) if period_type else f"{period_number} период"
    
    if state == "subjects":
        subject_name = data["subjects"][subject]["subject_name"]

        text = f"{await get_emoji_subject(subject_name)} <b>{subject_name}</b> ({period_display})\n"
        text += f'    🎓 <i>Всего оценок:</i> <span class="tg-spoiler">{data["subjects"][subject]["total_marks"]}</span>\n'
        text += f'    🏅 <i>Самая частая оценка:</i> <span class="tg-spoiler">{data["subjects"][subject]["frequent_grade"]}</span>\n'
        text += f'    📈 <i>Балл:</i> <span class="tg-spoiler">{data["subjects"][subject]["mark"]}</span>\n\n'
        
        total_marks = data["subjects"][subject]["total_marks"]
        
        text += f"    📔 <b>Оценки:</b>\n"
        for grade, count in sorted(
            data["subjects"][subject]["marks_count"].items(), reverse=True
        ):
            sticker = marks_emoji.get(int(grade), "📊")
            percentage = round(count / total_marks * 100, 1) if total_marks > 0 else 0
            text += f'         {sticker}: <span class="tg-spoiler">{count} <i>({percentage}%)</i></span>\n'

    elif state == "overall_results":
        text = f"<b>Общие результаты</b> ({period_display})\n"
        
        # Информация о периоде
        if "period_start" in data and "period_end" in data:
            start_date = await parse_date(data["period_start"])
            end_date = await parse_date(data["period_end"])
            if start_date != "Н/Д" and end_date != "Н/Д":
                text += f'    📅 <i>Период:</i> <span class="tg-spoiler">{start_date.strftime("%d.%m.%Y")} - {end_date.strftime("%d.%m.%Y")}</span>\n'
                if "period_duration_days" in data:
                    text += f'    ⏱ <i>Длительность:</i> <span class="tg-spoiler">{data["period_duration_days"]} дней</span>\n'
        
        # Основная статистика по оценкам
        text += f'    📝 <i>Общее количество оценок:</i> <span class="tg-spoiler">{data["total_grades"]}</span>\n'
        text += f'    🏅 <i>Самая частая оценка:</i> <span class="tg-spoiler">{data["frequent_grade_overall"]}</span>\n'
        text += f'    🌟 <i>Больше всего оценок:</i> <span class="tg-spoiler">{await get_emoji_subject(data["most_resolutive_subject"]["name"])} {data["most_resolutive_subject"]["name"]} - {data["most_resolutive_subject"]["marks_count"]}</span>\n'
        
        grades_count = data["grades_count"]
        total_grades = data["total_grades"]
        
        if total_grades > 0:
            # Лучший предмет по среднему баллу
            best_subject = None
            best_avg = 0
            for subject_info in data["subjects"]:
                if subject_info["total_marks"] > 0 and subject_info["mark"] != "Н/Д":
                    try:
                        avg = float(subject_info["mark"])
                        if avg > best_avg:
                            best_avg = avg
                            best_subject = subject_info["subject_name"]
                    except:
                        pass
        
        text += f'    🥇 <i>Лучший предмет:</i> <span class="tg-spoiler">{await get_emoji_subject(best_subject)} {best_subject} - {best_avg}</span>\n'
        
        
        if total_grades > 0:
            # Средний балл
            total_sum = sum(int(grade) * count for grade, count in grades_count.items())
            avg_grade = round(total_sum / total_grades, 2)
            text += f'    📊 <i>Средний балл за период:</i> <span class="tg-spoiler">{avg_grade}</span>\n\n'

        # Детализация оценок
        text += "    📔 <b>Оценки:</b>\n"
        for grade, count in sorted(data["grades_count"].items(), reverse=True):
            sticker = marks_emoji.get(int(grade), "📊")
            percentage = round(count / total_grades * 100, 1) if total_grades > 0 else 0
            text += f'         {sticker}: <span class="tg-spoiler">{count} <i>({percentage}%)</i></span>\n'

        # Статистика по домашним заданиям
        text += f'\n    📚 <b>Домашние задания:</b>\n'
        
        most_hw_date = await parse_date(data["most_homework_date"])
        least_hw_date = await parse_date(data["least_homework_date"])
        
        text += f'        📈 <i>Больше всего ДЗ:</i> <span class="tg-spoiler">{most_hw_date.strftime("%d %B") if most_hw_date != "Н/Д" else "Н/Д"} ({data["most_homework_count"]})</span>\n'
        text += f'        📉 <i>Меньше всего ДЗ:</i> <span class="tg-spoiler">{least_hw_date.strftime("%d %B") if least_hw_date != "Н/Д" else "Н/Д"} ({data["least_homework_count"]})</span>\n'
        text += f'        📊 <i>Среднее в день:</i> <span class="tg-spoiler">{data["avg_homework_count"]}</span>\n'
        
        # Дополнительная статистика по ДЗ (если есть)
        if "total_homework_days" in data:
            text += f'        📅 <i>Дней с ДЗ:</i> <span class="tg-spoiler">{data["total_homework_days"]}</span>\n'

        # Статистика посещаемости
        text += f'\n    🏫 <b>Посещаемость:</b>\n'
        
        attendance_rate = data.get("attendance_rate", 0)
        attendance_emoji = "✅" if attendance_rate >= 95 else "⚠️" if attendance_rate >= 80 else "❌"
        
        text += f'        {attendance_emoji} <i>Посещаемость:</i> <span class="tg-spoiler">{data["visited_days"]}/{data["total_school_days"]} дней <i>({attendance_rate}%)</i></span>\n'
        
        if data.get("skipped_days", 0) > 0:
            text += f'        ⚠️ <i>Пропущено дней:</i> <span class="tg-spoiler">{data["skipped_days"]}</span>\n'
        else:
            text += f'        ✅ <i>Пропусков:</i> <span class="tg-spoiler">нет</span>\n'
        
        # Статистика по урокам
        if "total_lessons" in data and "avg_lessons_per_day" in data:
            text += f'        📚 <i>Всего уроков:</i> <span class="tg-spoiler">{data["total_lessons"]}</span>\n'
        
        # Время в школе
        text += f'\n    ⏰ <b>Время в школе:</b>\n'
        
        if "total_school_time" in data:
            text += f'        🕒 <i>Всего времени:</i> <span class="tg-spoiler">{data["total_school_time"]}</span>\n'
        
        if "avg_school_time_per_day" in data:
            text += f'        📊 <i>В среднем в день:</i> <span class="tg-spoiler">{data["avg_school_time_per_day"]}</span>\n'
        
        longest_date = await parse_date(data["longest_day"]["date"])
        shortest_date = await parse_date(data["shortest_day"]["date"])
        
        text += f'        ⏱ <i>Самый долгий день:</i> <span class="tg-spoiler">{longest_date.strftime("%d %B") if longest_date != "Н/Д" else "Н/Д"} - {await minutes_to_time(data["longest_day"]["duration"])}</span>\n'
        text += f'        ⏳ <i>Самый короткий день:</i> <span class="tg-spoiler">{shortest_date.strftime("%d %B") if shortest_date != "Н/Д" else "Н/Д"} - {await minutes_to_time(data["shortest_day"]["duration"])}</span>\n'
        
        earliest_date = await parse_date(data["earliest_in"]["date"])
        latest_date = await parse_date(data["latest_out"]["date"])
        
        text += f'        🌅 <i>Самый ранний приход:</i> <span class="tg-spoiler">{earliest_date.strftime("%d %B") if earliest_date != "Н/Д" else "Н/Д"} - {data["earliest_in"]["time"]}</span>\n'
        text += f'        🌇 <i>Самый поздний уход:</i> <span class="tg-spoiler">{latest_date.strftime("%d %B") if latest_date != "Н/Д" else "Н/Д"} - {data["latest_out"]["time"]}</span>\n'
        
        # Дополнительная аналитика (если есть)
        if "max_lessons_day" in data and "max_lessons_count" in data:
            day_translation = {
                "Monday": "понедельник",
                "Tuesday": "вторник", 
                "Wednesday": "среду",
                "Thursday": "четверг",
                "Friday": "пятницу",
                "Saturday": "субботу",
                "Sunday": "воскресенье"
            }
            max_day = day_translation.get(data["max_lessons_day"], data["max_lessons_day"])
            text += f'        📊 <i>Самый загруженный день:</i> <span class="tg-spoiler">{max_day} ({data["max_lessons_count"]} уроков)</span>\n'
        
        if "max_subject_by_lessons" in data and "max_subject_lessons_count" in data:
            text += f'        📚 <i>Больше всего уроков:</i> <span class="tg-spoiler">{await get_emoji_subject(data["max_subject_by_lessons"])} {data["max_subject_by_lessons"]} - {data["max_subject_lessons_count"]}</span>\n'

    return text