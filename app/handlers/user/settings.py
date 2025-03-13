from aiogram import F, Router, Bot
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery, InputMediaPhoto
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext

from config import BOT_VERSION, DEVELOPER, DEVELOPER_SITE
import app.keyboards.user.keyboards as kb
from app.utils.database import AsyncSessionLocal, db, User, Settings


router = Router()


@router.message(F.text == "⚙️ Настройки")
async def settings(message: Message):
    text = f"⚙️ <b>Настройки</b>\n\n🤖 <b>Информация о боте</b>\n    - 📦 <b>Версия бота:</b> {BOT_VERSION}\n    - 👨‍💻 <b>Разработчик:</b> {DEVELOPER}\n    - 🌐 <b>Сайт разработчика:</b> {DEVELOPER_SITE}"

    await message.answer(
        text,
        reply_markup=await kb.user_settings(message.from_user.id),
        disable_web_page_preview=True,
    )


@router.callback_query(F.data == "enable_new_mark_notification_settings")
async def enable_new_mark_notification_settings(callback: CallbackQuery):
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            db.select(Settings).filter_by(user_id=callback.from_user.id)
        )
        settings = result.scalar_one_or_none()

        if settings:
            settings.enable_new_mark_notification = (
                not settings.enable_new_mark_notification
            )
            await session.commit()

        await callback.answer()
        await callback.message.edit_text(
            text=callback.message.text,
            reply_markup=await kb.user_settings(callback.from_user.id),
        )


@router.callback_query(F.data == "enable_homework_notification_settings")
async def enable_new_mark_notification_settings(callback: CallbackQuery):
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            db.select(Settings).filter_by(user_id=callback.from_user.id)
        )
        settings = result.scalar_one_or_none()

        if settings:
            settings.enable_homework_notification = (
                not settings.enable_homework_notification
            )
            await session.commit()

        await callback.answer()
        await callback.message.edit_text(
            text=callback.message.text,
            reply_markup=await kb.user_settings(callback.from_user.id),
        )


@router.callback_query(F.data == "experimental_features_settings")
async def experimental_features_settings(callback: CallbackQuery):
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            db.select(Settings).filter_by(user_id=callback.from_user.id)
        )
        settings = result.scalar_one_or_none()

        if settings:
            settings.experimental_features = not settings.experimental_features
            await session.commit()

        await callback.answer()
        await callback.message.answer(
            "⚙️ Обновление настроек", reply_markup=await kb.main(callback.from_user.id)
        )
        await callback.message.edit_text(
            text=callback.message.text,
            reply_markup=await kb.user_settings(callback.from_user.id),
        )



