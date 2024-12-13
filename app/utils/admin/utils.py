from aiogram import types
from functools import wraps

from app.utils.database import AsyncSessionLocal, db, User
from config import ADMIN_USERS, ERROR_MESSAGE


def admin_required(func):
    @wraps(func)
    async def wrapper(message: types.Message, *args, **kwargs):
        if message.from_user.id in ADMIN_USERS:
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


