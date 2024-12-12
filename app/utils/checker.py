from datetime import datetime, timedelta
from aiogram import Bot

from app.utils.database import AsyncSessionLocal, db, User
from app.utils.user.utils import get_notifications
import app.keyboards.user.keyboards as kb


async def new_notifications_checker(bot: Bot):
    async with AsyncSessionLocal() as session:
        result = await session.execute(db.select(User))
        users = result.scalars().all()
        
        for user in users:
            result = await get_notifications(user.user_id, is_checker=True)
            if result:
                chat = await bot.get_chat(user.user_id)
                await bot.send_message(chat_id=chat.id, text=result, reply_markup=kb.delete_message)