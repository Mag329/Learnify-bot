import os
from datetime import datetime, timedelta

from aiogram import Bot, F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, FSInputFile, InputMediaPhoto, Message
from octodiary.apis import AsyncMobileAPI
from octodiary.urls import Systems

import app.keyboards.admin.keyboards as kb
import app.keyboards.user.keyboards as user_kb
from app.config.config import (LOG_FILE, UPDATE_NOTIFICATION_FOOTER,
                               UPDATE_NOTIFICATION_HEADER)
from app.states.admin.states import UpdateNotificationState
from app.utils.admin.utils import admin_required, main_page
from app.utils.database import AsyncSessionLocal, Settings, User, db

router = Router()


@router.message(Command(commands="admin"))
@admin_required
async def admin_handler(message: Message):
    await message.answer(
        await main_page(),
        reply_markup=kb.panel,
    )


@router.callback_query(F.data == "update_notification")
async def update_notification_handler(callback: CallbackQuery, state: FSMContext):
    await callback.answer()

    await state.set_state(UpdateNotificationState.text)

    await callback.message.edit_text(
        text="Отправьте текст для рассылки",
        reply_markup=kb.back_to_admin_panel,
    )


@router.callback_query(F.data == "back_to_admin_panel")
async def back_to_admin_panel_handler(callback: CallbackQuery, state: FSMContext):
    await callback.answer()

    await callback.message.edit_text(
        await main_page(),
        reply_markup=kb.panel,
    )


@router.message(UpdateNotificationState.text)
@admin_required
async def update_notification_text_handler(message: Message, state: FSMContext):
    await state.update_data(text=message.text)

    await message.answer(
        f"<b>Предпросмотр:</b>\n\n{UPDATE_NOTIFICATION_HEADER}{message.text}{UPDATE_NOTIFICATION_FOOTER}",
        reply_markup=kb.confirm_update_notification,
    )

    await state.set_state(UpdateNotificationState.confirm)


@router.callback_query(F.data == "send_update_notification")
async def send_update_notification_handler(
    callback: CallbackQuery, state: FSMContext, bot: Bot
):
    await callback.answer()

    data = await state.get_data()

    async with AsyncSessionLocal() as session:
        await state.clear()

        result = await session.execute(db.select(User))
        users = result.scalars().all()

        for user in users:
            try:
                chat = await bot.get_chat(user.user_id)
                await bot.send_message(
                    chat_id=chat.id,
                    text=f"{UPDATE_NOTIFICATION_HEADER}{data['text']}{UPDATE_NOTIFICATION_FOOTER}",
                    reply_markup=await user_kb.main(user.user_id),
                )
            except Exception as e:
                continue

    await callback.message.edit_text(
        "Рассылка успешно отправлена",
        reply_markup=kb.back_to_admin_panel,
    )


@router.callback_query(F.data == "cancel_update_notification")
async def cancel_update_notification_handler(
    callback: CallbackQuery, state: FSMContext
):
    await callback.answer()

    await state.clear()

    await callback.message.edit_text(
        "Рассылка отменена",
        reply_markup=kb.back_to_admin_panel,
    )


@router.message(Command("logs"))
@admin_required
async def logs_handler(message: Message, state: FSMContext):
    if not os.path.exists(LOG_FILE):
        await message.answer("Лог-файл не найден.")
        return

    log_file = FSInputFile(LOG_FILE)  # Загружаем файл
    await message.answer_document(document=log_file, caption="")
