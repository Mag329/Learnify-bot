# SPDX-FileCopyrightText: 2024-2026 Mag329
#
# SPDX-License-Identifier: MIT

from functools import wraps

from aiogram import types
from envparse import Env
from loguru import logger

from app.config.config import ERROR_MESSAGE
from app.utils.database import get_session, User, db

env = Env()
env.read_envfile()


def admin_required(func):
    @wraps(func)
    async def wrapper(message: types.Message, *args, **kwargs):
        user_id = message.from_user.id
        admin_list = list(map(int, env.str("ADMIN_USERS").split(",")))
        if user_id in admin_list:
            logger.debug(f"Admin access granted for user {user_id}")
            return await func(message, *args, **kwargs)
        else:
            logger.warning(f"Unauthorized access attempt to admin function by user {user_id}")
            return None

    return wrapper


async def main_page():
    logger.info("Admin panel main page requested")
    
    try:
        async with await get_session() as session:
            logger.debug("Fetching users from database")
            result = await session.execute(db.select(User))
            users = result.scalars().all()
            
            users_count = len(users)
            logger.info(f"Found {users_count} users in database")

            text = f"⚙️ <b>Админ панель</b>\n\n<b>Пользователей в БД</b>: {users_count}"

    except Exception as e:
        logger.exception(f"Error loading admin main page: {e}")
        text = f"{ERROR_MESSAGE}\n<code>{e}</code>"

    return text
