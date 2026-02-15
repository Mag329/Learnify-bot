import os

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, FSInputFile, Message
from loguru import logger

import app.keyboards.admin.keyboards as kb
import app.keyboards.user.keyboards as user_kb
from app.config.config import ERRORS_LOG_FILE, LOG_FILE
from app.states.admin.states import UpdateNotificationState
from app.utils.admin.utils import admin_required, main_page
from app.utils.database import get_session, User, db

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
        f"<b>Предпросмотр:</b>\n\n{message.text}",
        reply_markup=kb.confirm_update_notification,
    )

    await state.set_state(UpdateNotificationState.confirm)


@router.callback_query(F.data == "send_update_notification")
async def send_update_notification_handler(
    callback: CallbackQuery, state: FSMContext, bot: Bot
):
    await callback.answer()

    data = await state.get_data()

    async with await get_session() as session:
        await state.clear()

        result = await session.execute(db.select(User))
        users = result.scalars().all()

        for user in users:
            try:
                chat = await bot.get_chat(user.user_id)
                await bot.send_message(
                    chat_id=chat.id,
                    text=f"{data['text']}",
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
    user_id = message.from_user.id
    logger.info(f"Admin {user_id} requested logs")
    
    # Проверка основного лог-файла
    if not os.path.exists(LOG_FILE):
        logger.warning(f"Log file not found: {LOG_FILE}")
        await message.answer("❌ Лог-файл не найден.")
        return
    
    # Проверка размера основного лог-файла
    log_size = os.path.getsize(LOG_FILE)
    if log_size == 0:
        logger.warning(f"Log file is empty: {LOG_FILE}")
        await message.answer("⚠️ Лог-файл пуст.")
    else:
        try:
            log_file = FSInputFile(LOG_FILE)
            await message.answer_document(
                document=log_file, 
                caption=f"📄 Основной лог ({log_size} bytes)"
            )
            logger.debug(f"Main log file sent to admin {user_id}, size: {log_size} bytes")
        except Exception as e:
            logger.exception(f"Error sending main log file to admin {user_id}: {e}")
            await message.answer(f"❌ Ошибка при отправке основного лог-файла: {e}")
    
    # Проверка файла с ошибками
    if not os.path.exists(ERRORS_LOG_FILE):
        logger.warning(f"Errors log file not found: {ERRORS_LOG_FILE}")
        await message.answer("⚠️ Файл с ошибками не найден.")
        return
    
    # Проверка размера файла с ошибками
    errors_size = os.path.getsize(ERRORS_LOG_FILE)
    if errors_size == 0:
        logger.warning(f"Errors log file is empty: {ERRORS_LOG_FILE}")
        await message.answer("⚠️ Файл с ошибками пуст.")
        return
    
    try:
        errors_log_file = FSInputFile(ERRORS_LOG_FILE)
        await message.answer_document(
            document=errors_log_file, 
            caption=f"❌ Лог ошибок ({errors_size} bytes)"
        )
        logger.debug(f"Errors log file sent to admin {user_id}, size: {errors_size} bytes")
        logger.success(f"Logs successfully sent to admin {user_id}")
    except Exception as e:
        logger.exception(f"Error sending errors log file to admin {user_id}: {e}")
        await message.answer(f"❌ Ошибка при отправке файла с ошибками: {e}")