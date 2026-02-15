from datetime import datetime, time

import redis.asyncio as redis

from app.config.config import (
    DEFAULT_CACHE_TTL,
    DEFAULT_LONG_CACHE_TTL,
    DEFAULT_MEDIUM_CACHE_TTL,
    DEFAULT_SHORT_CACHE_TTL,
    REDIS_HOST,
    REDIS_PORT,
)

redis_client = redis.Redis(
    host=REDIS_HOST, port=REDIS_PORT, db=0, decode_responses=True
)


async def invalidate_cache_for_notification(user_id, notification):
    event_type = notification.event_type

    if event_type in ["create_homework", "update_homework"]:
        date = notification.created_at
        pattern = f"homework:{user_id}:{date}:*"

        keys = await redis_client.keys(pattern)
        if keys:
            await redis_client.delete(*keys)


async def get_ttl():
    now = datetime.now()
    current_time = now.time()
    is_weekday = now.weekday() < 5  # Пн-Пт
    is_weekend = now.weekday() >= 5  # Сб-Вс

    school_start = time(7, 30)
    school_end = time(16, 30)

    evening_start = time(16, 30)
    evening_end = time(23, 0)

    night_start = time(23, 0)
    night_end = time(7, 30)

    if is_weekday:
        if school_start <= current_time < school_end:
            # Время уроков
            return DEFAULT_SHORT_CACHE_TTL
        elif evening_start <= current_time < evening_end:
            # Вечер
            return DEFAULT_MEDIUM_CACHE_TTL
        else:
            # Ночь
            return DEFAULT_LONG_CACHE_TTL
    elif is_weekend:
        if school_start <= current_time < evening_end:
            # Дневное время выходных
            return DEFAULT_MEDIUM_CACHE_TTL
        else:
            # Ночь выходных
            return DEFAULT_LONG_CACHE_TTL
    else:
        # По умолчанию
        return DEFAULT_CACHE_TTL


async def get_cache(key):
    cached_text = await redis_client.get(key)
    if cached_text and datetime.now().time() > time(16, 30):
        return cached_text
    return None


async def clear_user_cache(user_id: str):
    pattern = f"*:{user_id}:*"

    deleted = 0
    async for key in redis_client.scan_iter(match=pattern):
        await redis_client.delete(key)
        deleted += 1
    return deleted
