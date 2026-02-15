# SPDX-FileCopyrightText: 2024-2026 Mag329
#
# SPDX-License-Identifier: MIT

import json
from datetime import datetime, time

from learnifyapi.exceptions import APIError as LearnifyAPIError
from loguru import logger
from octodiary.exceptions import APIError

from app.keyboards import user as kb
from app.config.config import (
    ERROR_403_MESSAGE,
    ERROR_408_MESSAGE,
    ERROR_500_MESSAGE,
    ERROR_MESSAGE,
)
from app.utils.database import get_session, Settings, db
from app.utils.user.cache import get_ttl, redis_client


def handle_api_error():
    from app.utils.user.utils import user_send_message

    def decorator(func):
        async def wrapper(user_id, *args, **kwargs):
            logger.debug(f"Calling {func.__name__} for user {user_id}")

            try:
                result = await func(user_id, *args, **kwargs)
                logger.debug(
                    f"{func.__name__} completed successfully for user {user_id}"
                )
                return result
            except APIError as e:
                logger.error(
                    f"APIError ({e.status_code}) for user {user_id} in {func.__name__}: {e}"
                )

                if e.status_code in [401, 403]:
                    logger.warning(f"Auth error for user {user_id}, requesting reauth")
                    await user_send_message(user_id, ERROR_403_MESSAGE, kb.reauth)
                elif e.status_code == 408:
                    logger.warning(f"Timeout error for user {user_id}")
                    await user_send_message(
                        user_id, ERROR_408_MESSAGE, kb.delete_message
                    )
                elif e.status_code in [500, 501, 502]:
                    logger.error(f"Server error ({e.status_code}) for user {user_id}")
                    await user_send_message(
                        user_id, ERROR_500_MESSAGE, kb.delete_message
                    )
                else:
                    logger.error(f"Unknown API error for user {user_id}: {e}")
                    await user_send_message(user_id, ERROR_MESSAGE, kb.delete_message)

            except LearnifyAPIError as e:
                logger.error(
                    f"LearnifyAPIError ({e.status_code}) for user {user_id} in {func.__name__}: {e}"
                )

                if e.status_code == 403:
                    logger.warning(f"Learnify auth error for user {user_id}")
                    await user_send_message(
                        user_id, ERROR_403_MESSAGE, kb.delete_message
                    )
                else:
                    logger.error(f"Unknown Learnify error for user {user_id}: {e}")
                    await user_send_message(user_id, ERROR_MESSAGE, kb.delete_message)

            except Exception as e:
                logger.exception(
                    f"Unhandled exception for user {user_id} in {func.__name__}: {e}"
                )
                await user_send_message(user_id, ERROR_MESSAGE, kb.delete_message)

        return wrapper

    return decorator


def cache(ttl=None):
    def decorator(func):
        async def wrapper(*args, **kwargs):
            actual_ttl = ttl
            if not actual_ttl:
                actual_ttl = await get_ttl()
                logger.debug(f"Using default TTL: {actual_ttl}")

            # Извлекаем user_id и date_object из аргументов
            user_id = None
            date_object = None

            # Ищем user_id и date_object в позиционных аргументах
            if len(args) >= 2:
                user_id = args[0]
                date_object = args[1]
                logger.debug(
                    f"Found user_id={user_id}, date_object={date_object} in positional args"
                )

            else:
                # Ищем в ключевых аргументах
                user_id = kwargs.get("user_id")
                date_object = kwargs.get("date_object")
                logger.debug(
                    f"Found user_id={user_id}, date_object={date_object} in kwargs"
                )

            if not user_id or not date_object:
                # Если не нашли необходимые параметры, просто выполняем функцию
                logger.debug(
                    f"Missing required parameters for caching, executing {func.__name__} without cache"
                )
                return await func(*args, **kwargs)

            async with await get_session() as session:
                result = await session.execute(
                    db.select(Settings).filter_by(user_id=user_id)
                )
                settings: Settings = result.scalar_one_or_none()
                if settings and not (
                    settings.experimental_features and settings.use_cache
                ):
                    logger.debug(
                        f"Cache disabled for user {user_id}, executing {func.__name__}"
                    )
                    return await func(*args, **kwargs)
                elif settings:
                    logger.debug(f"Cache enabled for user {user_id}")

            cache_key = f"{func.__name__}:{user_id}:{date_object.strftime('%Y-%m-%d')}"
            logger.debug(f"Cache key: {cache_key}")

            # Пытаемся получить данные из кэша
            cached_data = await redis_client.get(cache_key)

            if cached_data and datetime.now().time() > time(16, 30):
                logger.debug(f"Cache hit for {cache_key}")
                data = json.loads(cached_data)
                return data["text"], datetime.strptime(data["date"], "%Y-%m-%d")
            elif cached_data:
                logger.debug(f"Cache hit but time condition not met (before 16:30)")
            else:
                logger.debug(f"Cache miss for {cache_key}")

            # Если данных нет в кэше, выполняем функцию
            logger.debug(f"Executing {func.__name__} for user {user_id}")
            result = await func(*args, **kwargs)

            # Сохраняем результат в кэш
            if result and len(result) == 2:
                text, date_obj = result
                cache_data = {"text": text, "date": date_obj.strftime("%Y-%m-%d")}
                await redis_client.setex(cache_key, actual_ttl, json.dumps(cache_data))
                logger.debug(f"Cached result for {cache_key} with TTL {actual_ttl}")
            else:
                logger.debug(f"Result not suitable for caching")

            return result

        return wrapper

    return decorator


def cache_text_only(ttl=None):
    def decorator(func):
        async def wrapper(*args, **kwargs):
            actual_ttl = ttl
            if not actual_ttl:
                actual_ttl = await get_ttl()
                logger.debug(f"Using default TTL: {actual_ttl}")

            cache_key_parts = []

            # Ищем user_id в аргументах
            user_id = None
            for arg in args:
                if isinstance(arg, int):
                    user_id = arg
                    logger.debug(f"Found user_id={user_id} in positional args")
                    break

            if not user_id:
                user_id = kwargs.get("user_id")
                if user_id:
                    logger.debug(f"Found user_id={user_id} in kwargs")

            # Добавляем user_id в ключ
            if user_id:
                cache_key_parts.append(f"user:{user_id}")

            # Добавляем subject_id если есть
            subject_id = kwargs.get("subject_id")
            if subject_id:
                cache_key_parts.append(f"subject:{subject_id}")
                logger.debug(f"Found subject_id={subject_id}")

            # Добавляем date_object если есть
            date_object = kwargs.get("date_object")
            if date_object and hasattr(date_object, "strftime"):
                cache_key_parts.append(f"date:{date_object.strftime('%Y-%m-%d')}")
                logger.debug(f"Found date_object={date_object.strftime('%Y-%m-%d')}")

            async with await get_session() as session:
                result = await session.execute(
                    db.select(Settings).filter_by(user_id=user_id)
                )
                settings: Settings = result.scalar_one_or_none()
                if settings and not (
                    settings.experimental_features and settings.use_cache
                ):
                    logger.debug(
                        f"Cache disabled for user {user_id}, executing {func.__name__}"
                    )
                    return await func(*args, **kwargs)
                elif settings:
                    logger.debug(f"Cache enabled for user {user_id}")

            # Создаем ключ кэша
            cache_key = f"text_only:{func.__name__}:{':'.join(cache_key_parts)}"
            logger.debug(f"Cache key: {cache_key}")

            # Пытаемся получить данные из кэша
            cached_text = await redis_client.get(cache_key)

            if cached_text:
                logger.debug(f"Cache hit for {cache_key}")
                return cached_text

            logger.debug(f"Cache miss for {cache_key}, executing {func.__name__}")

            # Если данных нет в кэше, выполняем функцию
            result = await func(*args, **kwargs)

            # Сохраняем результат в кэш
            if result:
                await redis_client.setex(cache_key, actual_ttl, result)
                logger.debug(f"Cached result for {cache_key} with TTL {actual_ttl}")
            else:
                logger.debug(f"Empty result, not caching")

            return result

        return wrapper

    return decorator
