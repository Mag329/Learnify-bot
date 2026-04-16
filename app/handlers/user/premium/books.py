# SPDX-FileCopyrightText: 2024-2026 Mag329
#
# SPDX-License-Identifier: MIT

import os
from datetime import datetime, timedelta
from loguru import logger

from aiogram import Bot, F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    BufferedInputFile,
    CallbackQuery,
    LabeledPrice,
    Message,
    PreCheckoutQuery,
)
from miniopy_async import Minio
from miniopy_async.error import S3Error

from app.keyboards import user as kb
from app.config.config import MINIO_BUCKET_NAME, NO_PREMIUM_ERROR
from app.minio import get_minio_client
from app.states.user.states import (
    ChooseAmountForPaymentState,
    ChooseUserForGiftState,
    SelectBookState,
    SelectGdzUrlState,
)
from app.utils.database import (
    get_session,
    Gdz,
    PremiumSubscription,
    PremiumSubscriptionPlan,
    StudentBook,
    Transaction,
    UserData,
    db,
)
from app.utils.misc import sanitize_filename
from app.utils.user.api.learnify.subscription import (
    create_subscription,
    get_user_info,
    successful_payment,
)
from app.utils.user.utils import get_student

router = Router()


@router.callback_query(F.data == "student_book_settings")
async def student_book_settings_handler(callback: CallbackQuery):
    user_id = callback.from_user.id
    logger.info(f"User {user_id} opened student book settings")
    
    async with await get_session() as session:
        result = await session.execute(
            db.select(StudentBook).filter_by(user_id=user_id)
        )
        books = result.scalars().all()
        
        logger.debug(f"User {user_id} has {len(books)} books configured")

        text = (
            f"📖 <b>Настройка электронных учебников</b>\n\n"
            f"📚 Отправьте файлы учебников для быстрого доступа к ним\n\n"
            f"🔗 <b>Текущие предметы:</b>\n"
            f"{'• ' + '\n• '.join([book.subject_name for book in books]) if books else '— пока ничего не добавлено —'}\n\n"
            f"👇 Выберите предмет ниже, чтобы изменить или добавить файл учебника"
        )

        await callback.answer()
        await callback.message.edit_text(
            text=text,
            reply_markup=await kb.choice_subject(user_id, "book"),
        )


@router.callback_query(F.data.startswith("select_subject_book_"))
async def select_subject_auto_gdz_handler(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    subject_id = int(callback.data.split("_")[-1])
    
    logger.info(f"User {user_id} selecting book for subject_id={subject_id}")

    await state.update_data(subject_id=subject_id)
    await state.set_state(SelectBookState.file)

    await callback.message.edit_text(
        "📖 <b>Отправьте файл учебника</b>", reply_markup=kb.delete_message
    )


@router.message(F.document)
async def select_book_handler(message: Message, state, bot):
    user_id = message.from_user.id
    data = await state.get_data()
    subject_id = data.get("subject_id")

    if not subject_id:
        logger.warning(f"User {user_id} sent document but no subject_id in state")
        await message.answer(
            "❌ <b>Предмет не найден</b>\nПопробуйте выбрать его заново"
        )
        return

    logger.info(f"User {user_id} uploading book for subject_id={subject_id}")
    logger.debug(f"Document: {message.document.file_name} ({message.document.file_size} bytes)")
    
    api, user = await get_student(message.from_user.id)
    subjects = await api.get_subjects(
        student_id=user.student_id, profile_id=user.profile_id
    )
    subject_name = next(
        (
            subject.subject_name
            for subject in subjects.payload
            if subject.subject_id == subject_id
        ),
        "Неизвестный предмет",
    )
    
    logger.debug(f"Subject name: {subject_name}")

    _, ext = os.path.splitext(message.document.file_name)
    ext = ext.lower() or ".pdf"
    safe_name = sanitize_filename(subject_name)
    object_name = f"{message.from_user.id}/{subject_id}/{safe_name}{ext}"

    logger.debug(f"MinIO object name: {object_name}")

    file = await bot.get_file(message.document.file_id)
    file_path = f"temp_{safe_name}{ext}"

    with open(file_path, "wb") as f:
        await bot.download_file(file.file_path, f)

    logger.debug(f"File downloaded to {file_path}")
    
    try:
        minio_client = await get_minio_client()
        await minio_client.fput_object(MINIO_BUCKET_NAME, object_name, file_path)
        logger.debug(f"File uploaded to MinIO: {object_name}")
        
        async with await get_session() as session:
            result = await session.execute(
            db.select(StudentBook).filter_by(
                    user_id=user_id, subject_id=subject_id
                )
            )
            book = result.scalar_one_or_none()
            if not book:
                book = StudentBook(
                    user_id=message.from_user.id,
                    subject_id=subject_id,
                    subject_name=subject_name,
                    file=object_name,
                )
                session.add(book)
            else:
                book.file = object_name
            await session.commit()
            
            logger.success(f"Book record created for user {user_id}, subject {subject_name}")

        await message.answer(
            "✅ Файл успешно загружен", reply_markup=kb.back_to_subscription_settings
        )

    except S3Error as e:
        logger.error(f"S3 error for user {user_id}: {e}")
        await message.reply(f"❌ <b>Ошибка при загрузке файла</b>")
    except Exception as e:
        logger.exception(f"Unexpected error for user {user_id}: {e}")
        await message.reply(f"❌ <b>Ошибка при загрузке файла</b>")
    finally:
        try:
            os.remove(file_path)
            logger.debug(f"Temporary file {file_path} removed")
        except FileNotFoundError:
            pass


@router.callback_query(F.data.startswith("student_book_"))
async def student_book_handler(callback: CallbackQuery):
    user_id = callback.from_user.id
    subject_id = int(callback.data.split("_")[-1])
    
    logger.info(f"User {user_id} requesting book for subject_id={subject_id}")

    await callback.answer()

    async with await get_session() as session:
        result = await session.execute(
            db.select(PremiumSubscription).filter_by(user_id=user_id)
        )
        premium_user = result.scalar_one_or_none()

        if not premium_user or not premium_user.is_active:
            logger.warning(f"User {user_id} attempted to access book without premium")
            await callback.message.answer(NO_PREMIUM_ERROR, reply_markup=kb.get_premium)
            return

        result = await session.execute(
            db.select(StudentBook).filter_by(
                user_id=user_id, subject_id=subject_id
            )
        )
        book = result.scalar_one_or_none()

        if not book:
            logger.warning(f"Book not found for user {user_id}, subject_id={subject_id}")
            await callback.message.answer(
                "❌ <b>Учебник не найден</b>", reply_markup=kb.set_student_book
            )
            return

        try:
            logger.debug(f"Fetching book from MinIO: {book.file}")
            minio_client = await get_minio_client()
            response = await minio_client.get_object(MINIO_BUCKET_NAME, book.file)
            data = await response.read()
            await response.release()
            
            logger.debug(f"Retrieved {len(data)} bytes from MinIO")

            file_name = book.file.split("/")[-1]
            file = BufferedInputFile(data, filename=file_name)
            temp_message = await callback.message.answer(f"Загрузка...")
            await callback.message.answer_document(document=file)
            await temp_message.delete()
            logger.success(f"Book sent to user {user_id}, file: {file_name}")

        except S3Error as e:
            logger.error(f"S3 error for user {user_id}: {e}")
            await callback.message.answer(
                "❌ <b>Ошибка при получении файла</b>", reply_markup=kb.delete_message
            )
        except Exception as e:
            logger.exception(f"Unexpected error for user {user_id}: {e}")
            await callback.message.answer(
                "⚠️ <b>Непредвиденная ошибка</b>", reply_markup=kb.delete_message
            )
