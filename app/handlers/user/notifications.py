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
            reply_markup=kb.notifications_all,
        )


@router.callback_query(F.data == "notifications_new")
async def notification_all_handler(callback: CallbackQuery):
    await callback.answer()
    text = await get_notifications(callback.from_user.id, False)
    if text:
        await callback.message.edit_text(
            text=text,
            reply_markup=kb.notifications_all,
        )


@router.callback_query(F.data == "notifications_all")
async def notification_all_handler(callback: CallbackQuery):
    await callback.answer()
    text = await get_notifications(callback.from_user.id, True)
    if text:
        await callback.message.edit_text(
            text=text,
            reply_markup=kb.notifications_new,
        )
