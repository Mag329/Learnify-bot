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
        settings: Settings = result.scalar_one_or_none()

        if settings:
            settings.enable_new_mark_notification = (
                not settings.enable_new_mark_notification
            )
            await session.commit()

        await callback.answer(f'Уведомления о новых оценках {"✅" if settings.enable_new_mark_notification else "❌"}\n\nПолучать уведомления о новых оценках', show_alert=True)
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
        settings: Settings = result.scalar_one_or_none()

        if settings:
            settings.enable_homework_notification = (
                not settings.enable_homework_notification
            )
            await session.commit()

        await callback.answer(f'Уведомления о новых ДЗ {"✅" if settings.enable_homework_notification else "❌"}\n\nПолучать уведомления о новых домашних заданиях', show_alert=True)
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
        settings: Settings = result.scalar_one_or_none()

        if settings:
            settings.experimental_features = not settings.experimental_features
            await session.commit()

        await callback.answer()
        await callback.message.edit_text(
            text=callback.message.text,
            reply_markup=await kb.user_settings(callback.from_user.id),
        )



@router.callback_query(F.data == "skip_empty_days_schedule_settings")
async def skip_empty_days_schedule_settings(callback: CallbackQuery):
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            db.select(Settings).filter_by(user_id=callback.from_user.id)
        )
        settings: Settings = result.scalar_one_or_none()

        if settings:
            settings.skip_empty_days_schedule = not settings.skip_empty_days_schedule
            await session.commit()

        await callback.answer(f'Пропускать пустые дни (расписание) {"✅" if settings.skip_empty_days_schedule else "❌"}\n\nНе показывать дни без уроков в расписании', show_alert=True)
        await callback.message.edit_text(
            text=callback.message.text,
            reply_markup=await kb.user_settings(callback.from_user.id),
        )
        

@router.callback_query(F.data == "skip_empty_days_homeworks_settings")
async def skip_empty_days_homeworks_settings(callback: CallbackQuery):
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            db.select(Settings).filter_by(user_id=callback.from_user.id)
        )
        settings: Settings = result.scalar_one_or_none()

        if settings:
            settings.skip_empty_days_homeworks = not settings.skip_empty_days_homeworks
            await session.commit()

        await callback.answer(f'Пропускать пустые дни (ДЗ) {"✅" if settings.skip_empty_days_homeworks else "❌"}\n\nНе показывать дни без домашних заданий', show_alert=True)
        await callback.message.edit_text(
            text=callback.message.text,
            reply_markup=await kb.user_settings(callback.from_user.id),
        )
        
        
@router.callback_query(F.data == "next_day_if_lessons_end_schedule_settings")
async def next_day_if_lessons_end_schedule_settings(callback: CallbackQuery):
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            db.select(Settings).filter_by(user_id=callback.from_user.id)
        )
        settings: Settings = result.scalar_one_or_none()

        if settings:
            settings.next_day_if_lessons_end_schedule = not settings.next_day_if_lessons_end_schedule
            await session.commit()

        await callback.answer(f'Расписание на следующий день {"✅" if settings.next_day_if_lessons_end_schedule else "❌"}\n\nПоказывать расписание на следующий день, если уроки в этот день закончились', show_alert=True)
        await callback.message.edit_text(
            text=callback.message.text,
            reply_markup=await kb.user_settings(callback.from_user.id),
        )
        
        
@router.callback_query(F.data == "next_day_if_lessons_end_homeworks_settings")
async def next_day_if_lessons_end_homeworks_settings(callback: CallbackQuery):
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            db.select(Settings).filter_by(user_id=callback.from_user.id)
        )
        settings: Settings = result.scalar_one_or_none()

        if settings:
            settings.next_day_if_lessons_end_homeworks = not settings.next_day_if_lessons_end_homeworks
            await session.commit()

        await callback.answer(f'ДЗ на завтра после уроков {"✅" if settings.next_day_if_lessons_end_homeworks else "❌"}\n\nПоказывать домашние задание на следующий день, если уроки в этот день закончились', show_alert=True)
        await callback.message.edit_text(
            text=callback.message.text,
            reply_markup=await kb.user_settings(callback.from_user.id),
        )