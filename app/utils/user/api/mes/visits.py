# SPDX-FileCopyrightText: 2024-2026 Mag329
#
# SPDX-License-Identifier: MIT

from datetime import datetime, timedelta

from aiogram.fsm.context import FSMContext
from loguru import logger

from app.keyboards import user as kb
from app.states.user.states import VisitState
from app.utils.user.cache import redis_client
from app.utils.user.decorators import handle_api_error
from app.utils.user.utils import get_student


@handle_api_error()
async def get_visits(user_id, date_object):
    logger.info(
        f"Getting visits for user {user_id}, date: {date_object.strftime('%Y-%m-%d')}"
    )

    cache_key = f"visits:{user_id}:{date_object.strftime('%Y-%m-%d')}"
    logger.debug(f"Cache key: {cache_key}")

    # Пытаемся получить данные из кэша
    cached_text = await redis_client.get(cache_key)
    if cached_text:
        logger.debug(
            f"Cache hit for visits: user {user_id}, date {date_object.strftime('%Y-%m-%d')}"
        )
        return cached_text

    logger.debug(
        f"Cache miss for visits: user {user_id}, date {date_object.strftime('%Y-%m-%d')}"
    )

    api, user = await get_student(user_id)
    if not api or not user:
        logger.error(f"Failed to get student data for user {user_id}")
        return "❌ <b>Ошибка</b>\n\nНе удалось получить данные ученика"

    date_start_week = date_object - timedelta(days=date_object.weekday())
    date_week_end = date_start_week + timedelta(days=6)

    logger.debug(
        f"Fetching visits for week: {date_start_week.strftime('%Y-%m-%d')} to {date_week_end.strftime('%Y-%m-%d')}"
    )

    visits = await api.get_visits(
        profile_id=user.profile_id,
        student_id=user.student_id,
        contract_id=user.contract_id,
        from_date=date_start_week,
        to_date=date_week_end,
    )

    if not visits.payload:
        logger.debug(f"No visits found for user {user_id} in specified week")
        text = f'📊 <b>Посещения за неделю ({date_start_week.strftime("%d.%m")}-{date_week_end.strftime("%d.%m")}):</b>\n\nНет данных о посещениях'
    else:
        visits = sorted(visits.payload, key=lambda x: x.date)
        logger.debug(f"Found {len(visits)} days with visits for user {user_id}")

    text = f'📊 <b>Посещения за неделю ({date_start_week.strftime("%d.%m")}-{date_week_end.strftime("%d.%m")}):</b>\n\n'

    for visit in visits:
        text += f'📅 <b>{visit.date.strftime("%d %B (%a)")}:</b>\n'
        for visit_in_day in visit.visits:
            text += f"    🔒 {visit_in_day.in_}\n    ⏱️ {visit_in_day.duration}\n    🔓 {visit_in_day.out}\n\n"

    # Сохраняем в кэш
    await redis_client.setex(cache_key, 7200, text)
    logger.debug(f"Cached visits for user {user_id} with TTL 7200s")

    return text


async def handle_visits_navigation(user_id: int, state: FSMContext, direction: str):
    logger.info(
        f"Handling visits navigation for user {user_id}, direction: {direction}"
    )

    data = await state.get_data()
    date = data.get("date", datetime.now())
    logger.debug(f"Current date from state: {date.strftime('%Y-%m-%d')}")

    if direction == "left":
        date -= timedelta(weeks=1)
        logger.debug(f"Moving left: new date {date.strftime('%Y-%m-%d')}")
    elif direction == "right":
        date += timedelta(weeks=1)
        logger.debug(f"Moving right: new date {date.strftime('%Y-%m-%d')}")
    elif direction == "week":
        date = datetime.now() - timedelta(
            days=datetime.now().weekday()
        )  # понедельник недели
        logger.debug(f"Moving to current week: {date.strftime('%Y-%m-%d')}")
    else:  # today
        date = datetime.now()
        logger.debug(f"Moving to today: {date.strftime('%Y-%m-%d')}")

    await state.set_state(VisitState.date)
    await state.update_data(date=date)

    try:
        text = await get_visits(user_id, date)
        logger.info(f"Successfully retrieved visits for user {user_id}")
        return text, kb.visits
    except Exception as e:
        logger.exception(f"Error in visits navigation for user {user_id}: {e}")
        return "❌ <b>Ошибка</b>\n\nНе удалось загрузить посещения", kb.visits
