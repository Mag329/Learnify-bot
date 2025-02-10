from aiogram import F, Router, Bot
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery, InputMediaPhoto
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext

from datetime import datetime, timedelta

from config import ERROR_MESSAGE
import app.keyboards.user.keyboards as kb
from app.utils.database import AsyncSessionLocal, db, User, Settings
from app.utils.user.utils import get_notifications


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
