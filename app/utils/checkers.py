import logging
from datetime import datetime, timedelta

from aiogram import Bot

import app.keyboards.user.keyboards as kb
from app.utils.database import AsyncSessionLocal, User, UserData, db
from app.utils.user.api.gigachat.birthday import birthday_greeting
from app.utils.user.api.mes.notifications import get_notifications
from app.utils.user.api.mes.replaces import get_replaces

logger = logging.getLogger(__name__)


async def new_notifications_checker(bot: Bot):
    async with AsyncSessionLocal() as session:
        result = await session.execute(db.select(User))
        users = result.scalars().all()

        for user in users:
            result = await get_notifications(user.user_id, all=False, is_checker=True)
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
            result = await get_replaces(user.user_id, datetime.now())
            if result:
                try:
                    chat = await bot.get_chat(user.user_id)
                    await bot.send_message(
                        chat_id=chat.id, text=result, reply_markup=kb.delete_message
                    )
                except Exception as e:
                    continue

            result = await get_replaces(
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

        today = datetime.now().date()

        for user in users:
            birthday = user.birthday
            if birthday is None:
                continue

            if birthday.date() == today:
                try:
                    chat = await bot.get_chat(user.user_id)
                    text = await birthday_greeting(user.first_name)

                    if not text:
                        text = (
                            f"{user.first_name}, <b>с днём рождения!</b> 🎉\n\n"
                            "Пусть каждый день приносит <i>новые открытия</i> и яркие эмоции. 📚\n"
                            "Желаем успехов в учёбе, <b>вдохновения</b> для новых достижений и море позитива! 🚀\n\n"
                            "<b>Learnify</b> всегда рядом, чтобы поддержать на пути к знаниям 💡"
                        )
                except Exception as e:
                    logger.error(
                        f"Failed to get chat or send birthday message for user_id={user.user_id}: {e}"
                    )
                    chat = None

                if chat:
                    await bot.send_message(
                        chat_id=chat.id, text=text, reply_markup=kb.delete_message
                    )
