# SPDX-FileCopyrightText: 2024-2026 Mag329
#
# SPDX-License-Identifier: MIT

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from loguru import logger

from app.keyboards import user as kb
from app.utils.user.api.mes.profile import get_profile
from app.utils.user.api.mes.rating import get_rating_rank_class
from app.utils.user.api.mes.visits import handle_visits_navigation

router = Router()


@router.message(F.text == "📋 Меню")
async def main_menu_handler(message: Message):
    user_id = message.from_user.id
    logger.debug(f"User {user_id} returned to main menu")
    
    await message.answer(
        "📋 Меню",
        reply_markup=await kb.menu(),
    )


@router.callback_query(
    F.data.in_({"visits", "visits_left", "visits_right", "visits_this_week"})
)
async def visits_navigation_handler(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    await callback.answer()

    data_key = callback.data
    direction_map = {
        "visits": "today",
        "visits_left": "left",
        "visits_right": "right",
        "visits_this_week": "week",
    }

    direction = direction_map.get(data_key, "today")
    logger.info(f"User {user_id} navigating visits: {direction}")

    text, markup = await handle_visits_navigation(
        user_id, state, direction
    )

    if text:
        await callback.message.edit_text(text=text, reply_markup=markup)
        logger.debug(f"Visits navigation successful for user {user_id}")
    else:
        logger.debug(f"No visits data for user {user_id}")
        await callback.message.edit_text(
            "📭 Посещений за выбранный период нет", reply_markup=markup
        )


@router.callback_query(F.data == "profile")
async def profile_callback_handler(callback: CallbackQuery):
    user_id = callback.from_user.id
    await callback.answer()

    logger.info(f"User {user_id} requested profile")
    
    text = await get_profile(user_id)
    if text:
        logger.debug(f"Profile sent to user {user_id}")
        await callback.message.edit_text(
            text=text,
            reply_markup=kb.back_to_menu,
        )


@router.callback_query(F.data == "rating_rank_class")
async def rating_rank_class_callback_handler(callback: CallbackQuery):
    user_id = callback.from_user.id
    await callback.answer()

    logger.info(f"User {user_id} requested class rating")
    
    text = await get_rating_rank_class(user_id)
    if text:
        logger.debug(f"Class rating sent to user {user_id}")
        await callback.message.edit_text(
            text=text,
            reply_markup=kb.back_to_menu,
        )


@router.callback_query(F.data == "back_to_menu")
async def back_to_menu_callback_handler(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    await callback.answer()

    await state.clear()
    logger.info(f"User {user_id} returned to main menu, state cleared")

    await callback.message.edit_text(
        text="📋 Меню",
        reply_markup=await kb.menu(),
    )
