# SPDX-FileCopyrightText: 2024-2026 Mag329
#
# SPDX-License-Identifier: MIT

import json
import socket
from datetime import datetime
from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from envparse import Env
from loguru import logger

from app.config.config import BOT_VERSION, LOGSTASH_HOST, LOGSTASH_PORT
from app.states.user.states import AuthState

env = Env()
env.read_envfile()


class StatsMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ):
        state = data.get("state")

        message_state = await state.get_state()

        if message_state in [
            AuthState.login,
            AuthState.password,
            AuthState.sms_code_class,
            AuthState.token,
        ]:
            logger.debug(f"Skipping stats for auth state: {message_state}")
            return await handler(event, data)
            
        user = None
        action_type = None
        action_data = None
        session_start = datetime.now()
        
        # Выполняем хендлер
        result = await handler(event, data)
        
        session_end = datetime.now()
        processing_time = (session_end - session_start).total_seconds() * 1000

        # Определяем тип действия и пользователя
        if event.message:
            action_type = "message"
            user = event.message.from_user
            action_data = event.message.text
            logger.debug(f"Processing message from user {user.id if user else 'unknown'}")

        elif event.callback_query:
            action_type = "callback_query"
            user = event.callback_query.from_user
            action_data = event.callback_query.data
            logger.debug(f"Processing callback query from user {user.id if user else 'unknown'}")

        # Отправка статистики в Logstash
        if user:
            user_info = {
                "user_id": user.id,
                "username": user.username,
                "full_name": user.full_name,
                "language_code": user.language_code,
            }

            # Формируем документ для отправки в Logstash
            doc = {
                "user": user_info,
                "action_type": action_type,
                "action_data": action_data,
                "timestamp": session_start.isoformat() + "Z",
                "processing_time_ms": processing_time,
                "bot_version": BOT_VERSION,
            }

            # Отправляем данные в Logstash
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.connect((LOGSTASH_HOST, LOGSTASH_PORT))
                sock.sendall((json.dumps(doc) + "\n").encode("utf-8"))
                sock.close()
                
                logger.debug(f"Stats sent to Logstash for user {user.id}, processing time: {processing_time:.2f}ms")
                
            except ConnectionRefusedError:
                logger.error(f"Connection refused to Logstash at {LOGSTASH_HOST}:{LOGSTASH_PORT}")
            except socket.gaierror:
                logger.error(f"Could not resolve Logstash host: {LOGSTASH_HOST}")
            except Exception as e:
                logger.exception(f"Failed to send data to Logstash: {e}")

        return
