from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery, Update
from typing import Callable, Dict, Any, Awaitable
import logging
import os

from config import START_MESSAGE, LOG_FILE
import app.keyboards.user.keyboards as kb
from app.utils.database import AsyncSessionLocal, db, User
from app.states.user.states import AuthState
from envparse import env


env.read_envfile()


# Создаем отдельный логгер для middleware
middleware_logger = logging.getLogger("middleware_logger")
middleware_logger.setLevel(logging.INFO)

# Проверяем наличие директории для логов
log_dir = os.path.dirname(LOG_FILE)  # Получаем путь к папке

if log_dir and not os.path.exists(log_dir):  # Если путь не пустой и папки нет
    os.makedirs(log_dir, exist_ok=True)  # Создаем папку

# Добавляем только файловый обработчик (без консоли)
file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
file_handler.setLevel(logging.INFO)
file_handler.setFormatter(
    logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
)

middleware_logger.addHandler(file_handler)
middleware_logger.propagate = (
    False  # Отключаем передачу логов в root-логгер (чтобы не дублировались)
)


class AllowedUsersMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ):
        if event.from_user.id in list(map(int, env.str("ALLOWED_USERS").split(","))):
            return await handler(event, data)


class CheckUserInDbMiddleware(BaseMiddleware):
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
        ):
            bot = event.bot

            message = event

            async with AsyncSessionLocal() as session:
                result = await session.execute(
                    db.select(User).filter_by(user_id=message.from_user.id)
                )
                user = result.scalar_one_or_none()

                if user:
                    return await handler(event, data)
                else:
                    await bot.send_message(
                        message.chat.id,
                        START_MESSAGE,
                        reply_markup=kb.start_command,
                    )
                    return
        else:
            return await handler(event, data)


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

        # Логируем вызов хэндлера
        # middleware_logger.info(f"Calling handler: {handler.__name__} with data: {data}")

        return await handler(event, data)
