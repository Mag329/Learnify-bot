from functools import wraps

from aiogram import types
from envparse import Env

from app.config.config import ERROR_MESSAGE
from app.utils.database import AsyncSessionLocal, User, db

env = Env()
env.read_envfile()


def admin_required(func):
    @wraps(func)
    async def wrapper(message: types.Message, *args, **kwargs):
        if message.from_user.id in list(map(int, env.str("ADMIN_USERS").split(","))):
            return await func(message, *args, **kwargs)
        else:
            return None

    return wrapper


async def main_page():
    try:
        async with AsyncSessionLocal() as session:
            result = await session.execute(db.select(User))
            users = result.scalars().all()

            text = f"⚙️ <b>Админ панель</b>\n\n<b>Пользователей в БД</b>: {len(users)}"

    except Exception as e:
        text = f"{ERROR_MESSAGE}\n<code>{e}</code>"

    return text
