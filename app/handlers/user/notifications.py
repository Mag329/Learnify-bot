from aiogram import F, Router
from aiogram.types import CallbackQuery, Message

import app.keyboards.user.keyboards as kb
from app.utils.user.api.mes.notifications import get_notifications

router = Router()


@router.message(F.text == "🔔 Уведомления")
async def notifications_handler(message: Message):
    text = await get_notifications(message.from_user.id)
    if text:
        await message.answer(
            text,
            reply_markup=kb.delete_message,
        )
