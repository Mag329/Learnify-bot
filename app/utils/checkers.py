from datetime import datetime, timedelta

from aiogram import Bot
from loguru import logger

import app.keyboards.user.keyboards as kb
from app.utils.database import get_session, User, UserData, db
from app.utils.user.api.gigachat.birthday import birthday_greeting
from app.utils.user.api.mes.notifications import get_notifications
from app.utils.user.api.mes.replaces import get_replaces


async def new_notifications_checker(bot: Bot):
    logger.info("Starting new notifications checker...")

    async with await get_session() as session:
        try:
            result = await session.execute(db.select(User))
            users = result.scalars().all()
            logger.debug(f"Found {len(users)} users to check for notifications")
        except Exception as e:
            logger.exception(f"Error fetching users for notifications checker: {e}")
            return

        sent_count = 0
        error_count = 0

        for user in users:
            try:
                result = await get_notifications(
                    user.user_id, all=False, is_checker=True
                )
                if result:
                    try:
                        chat = await bot.get_chat(user.user_id)
                        await bot.send_message(
                            chat_id=chat.id, text=result, reply_markup=kb.delete_message
                        )
                        sent_count += 1
                        logger.debug(f"Sent notification to user {user.user_id}")
                    except Exception as e:
                        error_count += 1
                        logger.debug(
                            f"Failed to send notification to user {user.user_id}: {e}"
                        )
                        continue
            except Exception as e:
                error_count += 1
                logger.error(
                    f"Error processing notifications for user {user.user_id}: {e}"
                )

        logger.info(
            f"Notifications checker completed. Sent: {sent_count}, Errors: {error_count}"
        )


async def replaced_checker(bot: Bot):
    logger.info("Starting replaced checker...")

    async with await get_session() as session:
        try:
            result = await session.execute(db.select(User))
            users = result.scalars().all()
            logger.debug(f"Found {len(users)} users to check for replacements")
        except Exception as e:
            logger.exception(f"Error fetching users for replaced checker: {e}")
            return

        today_count = 0
        tomorrow_count = 0
        error_count = 0

        for user in users:
            # Проверка на сегодня
            try:
                result_today = await get_replaces(user.user_id, datetime.now())
                if result_today:
                    try:
                        chat = await bot.get_chat(user.user_id)
                        await bot.send_message(
                            chat_id=chat.id,
                            text=result_today,
                            reply_markup=kb.delete_message,
                        )
                        today_count += 1
                        logger.debug(
                            f"Sent today's replacements to user {user.user_id}"
                        )
                    except Exception as e:
                        error_count += 1
                        logger.debug(
                            f"Failed to send today's replacements to user {user.user_id}: {e}"
                        )
            except Exception as e:
                error_count += 1
                logger.error(
                    f"Error processing today's replacements for user {user.user_id}: {e}"
                )

            # Проверка на завтра
            try:
                result_tomorrow = await get_replaces(
                    user.user_id, datetime.now() + timedelta(days=1)
                )
                if result_tomorrow:
                    try:
                        chat = await bot.get_chat(user.user_id)
                        await bot.send_message(
                            chat_id=chat.id,
                            text=result_tomorrow,
                            reply_markup=kb.delete_message,
                        )
                        tomorrow_count += 1
                        logger.debug(
                            f"Sent tomorrow's replacements to user {user.user_id}"
                        )
                    except Exception as e:
                        error_count += 1
                        logger.debug(
                            f"Failed to send tomorrow's replacements to user {user.user_id}: {e}"
                        )
            except Exception as e:
                error_count += 1
                logger.error(
                    f"Error processing tomorrow's replacements for user {user.user_id}: {e}"
                )

        logger.info(
            f"Replaced checker completed. Today: {today_count}, Tomorrow: {tomorrow_count}, Errors: {error_count}"
        )


async def birthday_checker(bot: Bot):
    logger.info("Starting birthday checker...")

    async with await get_session() as session:
        try:
            result = await session.execute(db.select(UserData))
            users = result.scalars().all()
            logger.debug(f"Found {len(users)} users with birthday data")
        except Exception as e:
            logger.exception(f"Error fetching users for birthday checker: {e}")
            return

        today = datetime.now().date()
        logger.debug(f"Checking birthdays for date: {today}")

        birthday_count = 0
        sent_count = 0
        error_count = 0

        for user in users:
            birthday = user.birthday
            if birthday is None:
                continue

            if birthday.date() == today:
                birthday_count += 1
                logger.info(
                    f"Today is {user.first_name}'s (ID: {user.user_id}) birthday!"
                )

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
                        logger.debug("Using default birthday greeting text")

                except Exception as e:
                    error_count += 1
                    logger.error(
                        f"Failed to get chat or send birthday message for user_id={user.user_id}: {e}"
                    )
                    chat = None

                if chat:
                    await bot.send_message(chat_id=chat.id, text=text)

        if birthday_count == 0:
            logger.info("No birthdays today")
        else:
            logger.success(
                f"Birthday checker completed. Found: {birthday_count}, Sent: {sent_count}, Errors: {error_count}"
            )
