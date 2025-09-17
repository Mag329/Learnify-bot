from datetime import datetime, timedelta

from aiogram.fsm.context import FSMContext

import app.keyboards.user.keyboards as kb
from app.states.user.states import VisitState
from app.utils.user.cache import redis_client
from app.utils.user.decorators import handle_api_error
from app.utils.user.utils import get_student


@handle_api_error()
async def get_visits(user_id, date_object):
    cache_key = f"visits:{user_id}:{date_object.strftime('%Y-%m-%d')}"

    # Пытаемся получить данные из кэша
    cached_text = await redis_client.get(cache_key)
    if cached_text:
        return cached_text

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

    visits = sorted(visits.payload, key=lambda x: x.date)

    text = f'📊 <b>Посещения за неделю ({date_start_week.strftime("%d.%m")}-{date_week_end.strftime("%d.%m")}):</b>\n\n'

    for visit in visits:
        text += f'📅 <b>{visit.date.strftime("%d %B (%a)")}:</b>\n'
        for visit_in_day in visit.visits:
            text += f"    🔒 {visit_in_day.in_}\n    ⏱️ {visit_in_day.duration}\n    🔓 {visit_in_day.out}\n\n"

    await redis_client.setex(cache_key, 7200, text)

    return text


async def handle_visits_navigation(user_id: int, state: FSMContext, direction: str):
    data = await state.get_data()
    date = data.get("date", datetime.now())

    if direction == "left":
        date -= timedelta(weeks=1)
    elif direction == "right":
        date += timedelta(weeks=1)
    elif direction == "week":
        date = datetime.now() - timedelta(
            days=datetime.now().weekday()
        )  # понедельник недели
    else:  # today
        date = datetime.now()

    await state.set_state(VisitState.date)
    await state.update_data(date=date)

    text = await get_visits(user_id, date)
    return text, kb.visits
