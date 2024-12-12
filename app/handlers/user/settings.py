from aiogram import F, Router, Bot
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery, InputMediaPhoto
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext

import app.keyboards.user.keyboards as kb
from app.utils.database import AsyncSessionLocal, db, User, Settings


router = Router()


@router.message(F.text == "⚙️ Настройки")
async def settings(message: Message):
    await message.answer(
        "⚙️ Настройки", reply_markup=await kb.user_settings(message.from_user.id)
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


@router.callback_query(F.data == "exit_from_account")
async def exit_from_account(callback_query: CallbackQuery):
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            db.select(User).filter_by(user_id=callback_query.from_user.id)
        )
        user = result.scalar_one_or_none()
        if user:
            await session.delete(user)
            await session.commit()

            await callback_query.answer()
            await callback_query.message.edit_text(
                "🚪 Вы вышли из аккаунта", reply_markup=kb.start_command
            )
        else:
            await callback_query.answer()
            await callback_query.message.edit_text(
                "❌ Ошибка выхода из аккаунта", reply_markup=kb.start_command
            )
