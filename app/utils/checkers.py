from datetime import datetime, timedelta
from aiogram import Bot

from app.utils.database import AsyncSessionLocal, db, User, UserData
from app.utils.user.utils import get_notifications, get_replaced
import app.keyboards.user.keyboards as kb

from app.utils.user.gigachat_api import birthday_greeting


async def new_notifications_checker(bot: Bot):
    async with AsyncSessionLocal() as session:
        result = await session.execute(db.select(User))
        users = result.scalars().all()

        for user in users:
            result = await get_notifications(user.user_id, is_checker=True)
            if result:
                try:
                    chat = await bot.get_chat(user.user_id)
                    await bot.send_message(
                        chat_id=chat.id, text=result, reply_markup=kb.delete_message
                    )
                except Exception as e:
                    continue


async def replaced_checker(bot: Bot):
    async with AsyncSessionLocal() as session:
        result = await session.execute(db.select(User))
        users = result.scalars().all()

        for user in users:
            result = await get_replaced(user.user_id, datetime.now())
            if result:
                try:
                    chat = await bot.get_chat(user.user_id)
                    await bot.send_message(
                        chat_id=chat.id, text=result, reply_markup=kb.delete_message
                    )
                except Exception as e:
                    continue

            result = await get_replaced(
                user.user_id, datetime.now() + timedelta(days=1)
            )
            if result:
                try:
                    chat = await bot.get_chat(user.user_id)
                    await bot.send_message(
                        chat_id=chat.id, text=result, reply_markup=kb.delete_message
                    )
                except Exception as e:
                    continue


async def birthday_checker(bot: Bot):
    async with AsyncSessionLocal() as session:
        result = await session.execute(db.select(UserData))
        users = result.scalars().all()

        for user in users:
            birthday = user.birthday
            if birthday is None:
                continue

            if birthday.date() == datetime.now().date():
                try:
                    chat = await bot.get_chat(user.user_id)
                    
                    text = await birthday_greeting(user.first_name)
                    
                    if not text:
                        text = f"{user.first_name}, <b>С днём рождения!</b> 🎉\n\nПусть каждый день приносит <i>новые открытия</i> и яркие эмоции. 📚\nЖелаем успехов в учёбе, <b>вдохновения</b> для новых достижений и море позитива! 🚀\n<b>Learnify</b> всегда рядом, чтобы поддержать на пути к знаниям 💡"
                    
                    await bot.send_message(
                        chat_id=chat.id, text=text, reply_markup=kb.delete_message
                    )
                except Exception as e:
                    continue