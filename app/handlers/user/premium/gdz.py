# SPDX-FileCopyrightText: 2024-2026 Mag329
#
# SPDX-License-Identifier: MIT

import logging
from datetime import datetime, timedelta
from loguru import logger

from aiogram import Bot, F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, LabeledPrice, Message, PreCheckoutQuery
from aiogram.utils.media_group import MediaGroupBuilder

from app.keyboards import user as kb
from app.config.config import NO_PREMIUM_ERROR
from app.states.user.states import (
    ChooseAmountForPaymentState,
    ChooseUserForGiftState,
    QuickGdzState,
    SelectGdzUrlState,
)
from app.utils.database import (
    get_session,
    Gdz,
    PremiumSubscription,
    PremiumSubscriptionPlan,
    Transaction,
    UserData,
    db,
)
from app.utils.misc import clear_state_if_still_waiting
from app.utils.scheduler import scheduler
from app.utils.user.api.learnify.subscription import (
    create_subscription,
    get_gdz_answers,
    get_user_info,
    successful_payment,
)
from app.utils.user.utils import get_student

router = Router()


@router.callback_query(F.data.startswith("quick_gdz_"))
async def subject_homework_callback_handler(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    subject_id = int(callback.data.split("_")[-1])
    
    logger.info(f"User {user_id} requested quick GDZ for subject_id={subject_id}")

    await callback.answer()

    async with await get_session() as session:
        result = await session.execute(
            db.select(PremiumSubscription).filter_by(user_id=user_id)
        )
        premium_user = result.scalar_one_or_none()

        if not premium_user or not premium_user.is_active:
            logger.warning(f"User {user_id} attempted to use quick GDZ without premium")
            await callback.message.answer(NO_PREMIUM_ERROR, reply_markup=kb.get_premium)
            return

        result = await session.execute(
            db.select(Gdz).filter_by(
                user_id=user_id, subject_id=subject_id
            )
        )
        gdz_info = result.scalar_one_or_none()

        if not gdz_info:
            logger.warning(f"User {user_id} has no GDZ config for subject {subject_id}")
            text = "❌ <b>Не указана ссылка для автоматизации ГДЗ</b>\n\n"
            return await callback.message.answer(
                text, reply_markup=kb.set_auto_gdz_links
            )

        logger.debug(f"User {user_id} has GDZ config for subject {subject_id}: {gdz_info.search_by}")
        
        await callback.message.answer(
            "⚡️ <b>Быстрое ГДЗ</b>",
            reply_markup=await kb.quick_gdz(
                subject_id, gdz_info.book_url, gdz_info.search_by
            ),
        )


@router.callback_query(F.data.startswith("choose_quick_gdz_"))
async def subject_homework_callback_handler(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    subject_id = int(callback.data.split("_")[-1])
    
    logger.info(f"User {user_id} starting quick GDZ input for subject_id={subject_id}")

    await callback.answer()
    await state.update_data(subject_id=subject_id)
    await state.set_state(QuickGdzState.number)

    job_id = f"clear_state_{user_id}"

    existing_job = scheduler.get_job(job_id)
    if existing_job:
        scheduler.remove_job(job_id)
        logger.debug(f"Removed existing clear state job for user {user_id}")

    scheduler.add_job(
        clear_state_if_still_waiting,
        args=[state],
        trigger="date",
        run_date=datetime.now() + timedelta(minutes=2),
        id=job_id,
    )
    logger.debug(f"Scheduled state clear for user {user_id} in 2 minutes")    

    async with await get_session() as session:
        result = await session.execute(
            db.select(Gdz.search_by).filter_by(
                user_id=user_id, subject_id=subject_id
            )
        )
        search_by = result.scalar_one_or_none()

    search_by_list = {
        "pages": "страницы",
        "numbers": "задания",
        "paragraphs": "параграфа",
    }

    await callback.message.edit_text(
        f"✏️ <b>Введите номер {search_by_list.get(search_by, 'задания')} для открытия ГДЗ</b>",
        reply_markup=kb.delete_message,
    )


@router.message(StateFilter(QuickGdzState.number))
async def quick_gdz_number_handler(message: Message, state: FSMContext):
    user_id = message.from_user.id
    data = await state.get_data()
    subject_id = data.get("subject_id")
    number = message.text
    
    logger.info(f"User {user_id} entered number '{number}' for quick GDZ, subject_id={subject_id}")
    
    await message.delete()

    if subject_id:
        if number.isdigit():
            await state.clear()

            temp_message = await message.answer(f"🔄 Загрузка...")
            logger.debug(f"Fetching GDZ answers for user {user_id}, number={number}")

            text, solutions = await get_gdz_answers(
                user_id=user_id, subject_id=subject_id, number=number
            )

            await temp_message.delete()

            if not solutions:
                logger.warning(f"No solutions found for user {user_id}, number={number}")
                await message.answer(
                    "❌ <b>Ошибка</b>\n\nНе удалось получить ответы",
                    reply_markup=kb.delete_message,
                )
                return

            logger.success(f"Found {len(solutions)} solutions for user {user_id}, number={number}")
            
            await message.answer(
                text, reply_markup=kb.delete_message, protect_content=True
            )

            def chunked(iterable, n):
                for i in range(0, len(iterable), n):
                    yield iterable[i : i + n]

            total_images = 0
            for num, solution in enumerate(solutions, 1):
                images = solution["images"]
                text = solution["text"]
                total_images += len(images)

                image_chunks = list(chunked(images, 10))
                total_parts = len(image_chunks)

                for i, image_chunk in enumerate(image_chunks, start=1):
                    if total_parts > 1:
                        caption = f"{num}. {text}\n🧩 Часть {i}/{total_parts}"
                    else:
                        caption = f"{num}. {text}"

                    media_group = MediaGroupBuilder(caption=caption)
                    for image in image_chunk:
                        media_group.add_photo(media=image)

                    await message.answer_media_group(
                        media=media_group.build(), protect_content=True
                    )
            
            logger.debug(f"Sent {total_images} images in {len(solutions)} solutions to user {user_id}")
                    
            await message.answer(
                text="✅ <b>Выдача завершена</b>", reply_markup=kb.delete_message
            )
        else:
            logger.warning(f"User {user_id} entered non-digit input: '{number}'")
            await message.answer(
                "❌ <b>Ошибка</b>\n\nВведите число",
                reply_markup=kb.delete_message,
            )