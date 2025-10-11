import json
import logging
from datetime import datetime, time, timedelta

from learnifyapi.exceptions import APIError as LearnifyAPIError
from octodiary.exceptions import APIError

import app.keyboards.user.keyboards as kb
from app.config.config import (DEFAULT_SHORT_CACHE_TTL, ERROR_403_MESSAGE,
                               ERROR_408_MESSAGE, ERROR_500_MESSAGE,
                               ERROR_MESSAGE)
from app.utils.database import AsyncSessionLocal, Settings, db
from app.utils.user.cache import get_ttl, redis_client

logger = logging.getLogger(__name__)


def handle_api_error():
    from app.utils.user.utils import user_send_message

    def decorator(func):
        async def wrapper(user_id, *args, **kwargs):
            try:
                return await func(user_id, *args, **kwargs)
            except APIError as e:
                logger.error(f"APIError ({e.status_code}) for user {user_id}: {e}")

                if e.status_code in [401, 403]:
                    await user_send_message(user_id, ERROR_403_MESSAGE, kb.reauth)
                elif e.status_code == 408:
                    await user_send_message(
                        user_id, ERROR_408_MESSAGE, kb.delete_message
                    )
                elif e.status_code in [500, 501, 502]:
                    await user_send_message(
                        user_id, ERROR_500_MESSAGE, kb.delete_message
                    )
                else:
                    await user_send_message(user_id, ERROR_MESSAGE, kb.delete_message)
            except LearnifyAPIError as e:
                if e.status_code == 403:
                    await user_send_message(user_id, ERROR_403_MESSAGE, kb.delete_message)
                else:
                    await user_send_message(user_id, ERROR_MESSAGE, kb.delete_message)
            except Exception as e:
                logger.exception(f"Unhandled exception for user {user_id}: {e}")
                await user_send_message(user_id, ERROR_MESSAGE, kb.delete_message)

        return wrapper

    return decorator



def cache(ttl=None):
    def decorator(func):
        async def wrapper(*args, **kwargs):
            actual_ttl = ttl
            if not actual_ttl:
                actual_ttl = await get_ttl()

            # Извлекаем user_id и date_object из аргументов
            user_id = None
            date_object = None

            # Ищем user_id и date_object в позиционных аргументах
            if len(args) >= 2:
                user_id = args[0]
                date_object = args[1]
            else:
                # Ищем в ключевых аргументах
                user_id = kwargs.get("user_id")
                date_object = kwargs.get("date_object")

            if not user_id or not date_object:
                # Если не нашли необходимые параметры, просто выполняем функцию
                return await func(*args, **kwargs)

            async with AsyncSessionLocal() as session:
                result = await session.execute(
                    db.select(Settings).filter_by(user_id=user_id)
                )
                settings: Settings = result.scalar_one_or_none()
                if settings and not (
                    settings.experimental_features and settings.use_cache
                ):
                    return await func(*args, **kwargs)

            cache_key = f"{func.__name__}:{user_id}:{date_object.strftime('%Y-%m-%d')}"

            # Пытаемся получить данные из кэша
            cached_data = await redis_client.get(cache_key)

            if cached_data and datetime.now().time() > time(16, 30):
                data = json.loads(cached_data)
                return data["text"], datetime.strptime(data["date"], "%Y-%m-%d")

            # Если данных нет в кэше, выполняем функцию
            result = await func(*args, **kwargs)

            # Сохраняем результат в кэш
            if result and len(result) == 2:
                text, date_obj = result
                cache_data = {"text": text, "date": date_obj.strftime("%Y-%m-%d")}
                await redis_client.setex(cache_key, actual_ttl, json.dumps(cache_data))

            return result

        return wrapper

    return decorator


def cache_text_only(ttl=None):
    def decorator(func):
        async def wrapper(*args, **kwargs):
            actual_ttl = ttl
            if not actual_ttl:
                actual_ttl = await get_ttl()
            cache_key_parts = []

            # Ищем user_id в аргументах
            user_id = None
            for arg in args:
                if isinstance(arg, int):
                    user_id = arg
                    break

            if not user_id:
                user_id = kwargs.get("user_id")

            # Добавляем user_id в ключ
            if user_id:
                cache_key_parts.append(f"user:{user_id}")

            # Добавляем subject_id если есть
            subject_id = kwargs.get("subject_id")
            if subject_id:
                cache_key_parts.append(f"subject:{subject_id}")

            # Добавляем date_object если есть
            date_object = kwargs.get("date_object")
            if date_object and hasattr(date_object, "strftime"):
                cache_key_parts.append(f"date:{date_object.strftime('%Y-%m-%d')}")

            async with AsyncSessionLocal() as session:
                result = await session.execute(
                    db.select(Settings).filter_by(user_id=user_id)
                )
                settings: Settings = result.scalar_one_or_none()
                if settings and not (
                    settings.experimental_features and settings.use_cache
                ):
                    return await func(*args, **kwargs)

            # Создаем ключ кэша
            cache_key = f"text_only:{func.__name__}:{':'.join(cache_key_parts)}"

            # Пытаемся получить данные из кэша
            cached_text = await redis_client.get(cache_key)

            if cached_text:
                return cached_text

            # Если данных нет в кэше, выполняем функцию
            result = await func(*args, **kwargs)

            # Сохраняем результат в кэш
            if result:
                await redis_client.setex(cache_key, actual_ttl, result)

            return result

        return wrapper

    return decorator
