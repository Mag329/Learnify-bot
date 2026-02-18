# SPDX-FileCopyrightText: 2024-2026 Mag329
#
# SPDX-License-Identifier: MIT

from typing import Any, Awaitable, Callable, Dict
from loguru import logger

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from envparse import env

from app.keyboards import user as kb
from app.config.config import ALLOWED_USERS, LOG_FILE, NO_SUBSCRIPTION_TO_CHANNEL_ERROR
from app.utils.database import get_session, UserData, db
from app.utils.misc import check_subscription
from app.utils.user.utils import user_send_message

env.read_envfile()


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
            logger.info(f"Message from {user_info}: {event.message.text}")

        elif event.callback_query:
            user = event.callback_query.from_user
            user_info = f"{user.full_name} (@{user.username}, ID: {user.id})"
            logger.info(f"Callback from {user_info}: {event.callback_query.data}")

        return await handler(event, data)


class CheckSubscription(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ):
        if not (
            getattr(event, "message", None) or getattr(event, "callback_query", None)
        ):
            return await handler(event, data)

        if event.message:
            if event.message.text == "/start":
                logger.debug(f"User {event.message.from_user.id} started bot, skipping subscription check")
                return await handler(event, data)

            user_id = event.message.from_user.id
        elif event.callback_query:
            user_id = event.callback_query.from_user.id

        logger.debug(f"Checking subscription for user {user_id}")
        result = await check_subscription(user_id=user_id, bot=event.bot)
        
        if result:
            logger.debug(f"User {user_id} is subscribed, allowing access")
            return await handler(event, data)
        else:
            logger.warning(f"User {user_id} is not subscribed to channel, blocking access")
            await user_send_message(
                user_id, NO_SUBSCRIPTION_TO_CHANNEL_ERROR, kb.link_to_channel
            )


class AllowedUsersMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ):
        user_id = None
        
        if hasattr(event, "message") and event.message and event.message.from_user:
            user_id = event.message.from_user.id
        elif hasattr(event, "callback_query") and event.callback_query and event.callback_query.from_user:
            user_id = event.callback_query.from_user.id
        elif hasattr(event, "inline_query") and event.inline_query and event.inline_query.from_user:
            user_id = event.inline_query.from_user.id
        
        if user_id is not None:
            if user_id in ALLOWED_USERS:
                logger.debug(f"User {user_id} is in allowed users list")
                return await handler(event, data)
            else:
                logger.warning(f"User {user_id} is not in allowed users list, blocking access")
                return None
        logger.warning(f"Cannot determine user_id for event {event}, blocking access")
        return None


class UpdateUsernameMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ):
        user_id = None
        username = None

        if hasattr(event, "message") and event.message and event.message.from_user:
            user_id = event.message.from_user.id
            username = event.message.from_user.username
        elif hasattr(event, "callback_query") and event.callback_query and event.callback_query.from_user:
            user_id = event.callback_query.from_user.id
            username = event.callback_query.from_user.username
        elif hasattr(event, "inline_query") and event.inline_query and event.inline_query.from_user:
            user_id = event.inline_query.from_user.id
            username = event.inline_query.from_user.username
        
        async with await get_session() as session:
            result = await session.execute(
                db.select(UserData).filter_by(user_id=user_id)
            )
            user_data: UserData = result.scalar_one_or_none()
            if user_data and user_data.username != username:
                if username:
                    old_username = user_data.username
                    user_data.username = username
                    await session.commit()
                    logger.info(f"Updated username for user {user_id}: {old_username} -> {username}")
                else:
                    logger.debug(f"User {user_id} has no username in Telegram")
            elif not user_data:
                logger.debug(f"No UserData found for user {user_id}")
                
        return await handler(event, data)
