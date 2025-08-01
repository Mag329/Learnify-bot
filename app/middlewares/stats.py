import json
import logging
import socket
from datetime import datetime
from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject, Update
from envparse import Env

from app.config.config import BOT_VERSION, LOGSTASH_HOST, LOGSTASH_PORT
from app.states.user.states import AuthState

env = Env()
env.read_envfile()

# Настройка логирования
middleware_logger = logging.getLogger(__name__)


class StatsMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ):
        state = data.get("state")

        if (
            await state.get_state() != AuthState.login
            and await state.get_state() != AuthState.password
            and await state.get_state() != AuthState.sms_code_class
        ):
            user = None
            action_type = None
            action_data = None
            session_start = datetime.utcnow()

            # Логируем действия пользователя
            if event.message:
                action_type = "message"
                user = event.message.from_user
                action_data = event.message.text

            elif event.callback_query:
                action_type = "callback_query"
                user = event.callback_query.from_user
                action_data = event.callback_query.data

            if user:
                user_info = {
                    "user_id": user.id,
                    "username": user.username,
                    "full_name": user.full_name,
                    "language_code": user.language_code,
                }

                # Время обработки события
                session_end = datetime.utcnow()
                processing_time = (session_end - session_start).total_seconds() * 1000

                # Формируем документ для отправки в Logstash
                doc = {
                    "user": user_info,
                    "action_type": action_type,
                    "action_data": action_data,
                    "timestamp": session_start.isoformat(),
                    "processing_time_seconds": processing_time,
                    "bot_version": BOT_VERSION,  # Версия бота (можно добавить из конфига)
                }

                # Отправляем данные в Logstash
                try:
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.connect((LOGSTASH_HOST, LOGSTASH_PORT))
                    sock.sendall(json.dumps(doc).encode("utf-8"))
                    sock.close()
                except Exception as e:
                    middleware_logger.error(f"Failed to send data to Logstash: {e}")

            # Логируем вызов хэндлера
            middleware_logger.info(
                f"Calling handler: {handler.__name__} with data: {data}"
            )

        # Продолжаем выполнение хэндлера
        return await handler(event, data)
