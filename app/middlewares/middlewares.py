import logging
import os
from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from envparse import env

import app.keyboards.user.keyboards as kb
from app.config.config import LOG_FILE, NO_SUBSCRIPTION_ERROR
from app.utils.misc import check_subscription
from app.utils.user.utils import user_send_message

env.read_envfile()


# Создаем отдельный логгер для middleware
middleware_logger = logging.getLogger("middleware_logger")
middleware_logger.setLevel(logging.INFO)

log_dir = os.path.dirname(LOG_FILE)

if log_dir and not os.path.exists(log_dir):
    os.makedirs(log_dir, exist_ok=True)

file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
file_handler.setLevel(logging.INFO)
file_handler.setFormatter(
    logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
)

middleware_logger.addHandler(file_handler)
middleware_logger.propagate = (
    False  # Отключаем передачу логов в root-логгер (чтобы не дублировались)
)


class LoggingMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ):
        user = None
        if event.message:
            user = event.message.from_user
            user_info = f"{user.full_name} (@{user.username}, ID: {user.id})"
            middleware_logger.info(f"Message from {user_info}: {event.message.text}")

        elif event.callback_query:
            user = event.callback_query.from_user
            user_info = f"{user.full_name} (@{user.username}, ID: {user.id})"
            middleware_logger.info(
                f"CallbackQuery from {user_info}: {event.callback_query.data}"
            )

        return await handler(event, data)


class CheckSubscription(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ):
        if event.message:
            if event.message.text == "/start":
                return await handler(event, data)

            user_id = event.message.from_user.id
        elif event.callback_query:
            user_id = event.callback_query.from_user.id

        result = await check_subscription(user_id=user_id, bot=event.bot)
        if result:
            return await handler(event, data)
        else:
            await user_send_message(user_id, NO_SUBSCRIPTION_ERROR, kb.link_to_channel)
