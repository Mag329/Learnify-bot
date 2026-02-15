from aiogram import F, Router
from aiogram.types import CallbackQuery, Message
from loguru import logger

from app.keyboards import user as kb
from app.utils.user.api.mes.notifications import get_notifications

router = Router()


@router.message(F.text == "🔔 Уведомления")
async def notifications_handler(message: Message):
    user_id = message.from_user.id
    
    logger.info(f"User {user_id} requested notifications")
    
    text = await get_notifications(message.from_user.id)
    if text:
        await message.answer(
            text,
            reply_markup=kb.delete_message,
        )
